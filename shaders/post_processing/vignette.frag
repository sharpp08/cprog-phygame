// Dynamic cinematic vignette (fragment shader).
// Uniforms: t_scene, u_vignette (0..1), u_pulse (low-HP heartbeat 0..1),
// u_event (horror-event boost 0..1), u_tension (0..1)
precision mediump float;
uniform sampler2D t_scene;
uniform float u_vignette;
uniform float u_pulse;
uniform float u_event;
uniform float u_tension;
varying vec2 v_uv;

void main() {
    vec3 c = texture2D(t_scene, v_uv).rgb;
    vec2 p = v_uv * 2.0 - 1.0;                 // -1..1
    float r = length(p);
    float mask = clamp((r - 0.42) / 0.85, 0.0, 1.0);
    mask = pow(mask, 1.8);
    float strength = min(1.25,
                         u_vignette * (0.55 + 0.45 * u_tension)
                         + u_event * 0.6 + u_pulse * 0.5);
    c *= 1.0 - mask * 0.55 * strength;          // keep centre readable
    gl_FragColor = vec4(c, 1.0);
}
