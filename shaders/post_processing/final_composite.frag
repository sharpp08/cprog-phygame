// Fused final composite pass (fragment shader).
// Runs at NATIVE resolution in ONE pass: distortion -> chromatic
// aberration -> cinematic grade (+ low-HP desaturation) -> bloom glow
// composite -> vignette -> film grain -> damage / lightning flashes.
//
// The scene texture is sampled, never replaced with a low-res image:
// only the bloom glow (t_glow) comes from the small buffer, which is
// exactly what keeps the base image razor sharp.
//
// Uniforms:
//   t_scene          native-res scene texture
//   t_glow           low-res blurred thresholded-brights texture
//   u_res            native resolution (vec2)
//   u_grade          0..1 grade strength
//   u_lowhp          0..1 low-health desaturation
//   u_ca             0..1 eased chromatic-aberration amount
//   u_amount         0..1 eased spatial-distortion amount (events only)
//   u_time           seconds
//   u_tension        0..1 horror tension
//   u_vignette       preset vignette strength
//   u_pulse          low-HP heartbeat pulse (0..1)
//   u_event          horror-event vignette boost (0..1)
//   u_grain          preset grain strength
//   u_flash_red      damage flash (0..1)
//   u_flash_white    lightning flash (0..1)
//   u_bloom_strength final glow add amount (0..1)
precision highp float;
uniform sampler2D t_scene;
uniform sampler2D t_glow;
uniform vec2 u_res;
uniform float u_grade;
uniform float u_lowhp;
uniform float u_ca;
uniform float u_amount;
uniform float u_time;
uniform float u_tension;
uniform float u_vignette;
uniform float u_pulse;
uniform float u_event;
uniform float u_grain;
uniform float u_flash_red;
uniform float u_flash_white;
uniform float u_bloom_strength;
varying vec2 v_uv;

float hash(vec2 p) {
    p = fract(p * 0.3183099 + 0.1);
    p = p * 217.7;
    return fract(p.x * p.y * (p.x + p.y));
}

vec3 grade(vec3 c) {
    vec3 lut = c;
    float w = pow(1.0 - c.g, 2.0);
    lut.r = clamp(c.r * 1.02 + 0.008 - w * 0.02, 0.0, 1.0);
    lut.g = clamp(c.g * 0.98 + 0.004 - w * 0.008, 0.0, 1.0);
    lut.b = clamp(c.b * 1.05 + 0.016 + w * 0.024, 0.0, 1.0);
    float lum = dot(lut, vec3(0.299, 0.587, 0.114));
    lut = lut * 0.94 + lum * 0.06;
    return lut;
}

void main() {
    // 1) spatial distortion (only when an event has ramped it up)
    vec2 uv = v_uv;
    if (u_amount > 0.02) {
        float a = u_amount * 0.004;
        vec2 p = uv - 0.5;
        float d = length(p);
        vec2 warp = vec2(sin(uv.y * 11.0 + u_time * 2.1),
                         cos(uv.x * 13.0 - u_time * 1.7)) * a;
        warp += normalize(p + vec2(1e-6)) * sin(d * 14.0 - u_time * 3.0) * a * 0.5;
        uv += warp;
    }
    // 2) chromatic aberration, edge-weighted so the centre stays clean
    vec2 p = uv * 2.0 - 1.0;
    float r2 = dot(p, p);
    float off = u_ca * (0.0015 + 0.004 * u_ca + 0.001 * u_tension) * r2;
    vec2 dir = normalize(p + vec2(1e-6));
    vec3 c;
    if (off > 0.00001) {
        c = vec3(texture2D(t_scene, uv + dir * off).r,
                 texture2D(t_scene, uv).g,
                 texture2D(t_scene, uv - dir * off).b);
    } else {
        c = texture2D(t_scene, uv).rgb;
    }
    // 3) cinematic grade + low-HP desaturation
    c = mix(c, grade(c), u_grade);
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(c, vec3(lum), u_lowhp * 0.35);
    // 4) composite the (only low-res part of the pipeline) bloom glow
    c += texture2D(t_glow, v_uv).rgb * u_bloom_strength;
    // 5) vignette: darkens corners without touching the centre image
    vec2 q = v_uv * 2.0 - 1.0;
    float m = clamp((length(q) - 0.42) / 0.85, 0.0, 1.0);
    m = pow(m, 1.8);
    float strength = min(1.25,
                         u_vignette * (0.55 + 0.45 * u_tension)
                         + u_event * 0.6 + u_pulse * 0.5);
    c *= 1.0 - m * 0.55 * strength;
    // 6) animated film grain
    if (u_grain > 0.0) {
        float amt = u_grain * (0.0235 + 0.035 * u_tension + 0.055 * u_amount);
        vec2 g = floor(v_uv * u_res * 0.75) + floor(u_time * 60.0);
        c += (hash(g) - 0.5) * 2.0 * amt;
    }
    // 7) damage flash / lightning flash
    if (u_flash_red > 0.01) {
        c.r += 0.824 * u_flash_red;
        c.g *= (1.0 - 0.45 * u_flash_red);
        c.b *= (1.0 - 0.45 * u_flash_red);
    }
    if (u_flash_white > 0.01) {
        c += u_flash_white * 0.627 * vec3(0.75, 0.85, 1.0);
    }
    gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
