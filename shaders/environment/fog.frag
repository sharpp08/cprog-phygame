// Distance + height fog with flashlight interaction (fragment shader).
// Uniforms: t_scene, u_fog_color, u_fog_density (per-pixel scale),
// u_fog_min, u_fog_max (screen-space distance in 0..1 from centre),
// u_flash_pos (world-screen pos 0..1), u_flash_radius, u_flash_intensity
// Screen-space approximation: fog thickens toward the screen edges
// (farther tiles) and the flashlight clears a pool, so light "cuts
// through" the fog.
precision mediump float;
uniform sampler2D t_scene;
uniform vec3 u_fog_color;
uniform float u_fog_density;
uniform float u_fog_min;
uniform float u_fog_max;
uniform vec2 u_flash_pos;
uniform float u_flash_radius;
uniform float u_flash_intensity;
varying vec2 v_uv;

void main() {
    vec3 c = texture2D(t_scene, v_uv).rgb;
    // depth proxy: distance from the centre of the screen
    float depth = distance(v_uv, vec2(0.5));
    float t = clamp((depth - u_fog_min) / max(0.001, u_fog_max - u_fog_min),
                    0.0, 1.0);
    t *= u_fog_density;
    // height bias: lower half of the frame (ground) gets thicker fog
    t *= mix(1.15, 0.85, v_uv.y);
    // flashlight clears the fog near its position
    float fd = distance(v_uv, u_flash_pos);
    t *= 1.0 - clamp(1.0 - fd / max(0.001, u_flash_radius), 0.0, 1.0)
           * u_flash_intensity;
    t = clamp(t, 0.0, 1.0);
    gl_FragColor = vec4(mix(c, u_fog_color, t), 1.0);
}
