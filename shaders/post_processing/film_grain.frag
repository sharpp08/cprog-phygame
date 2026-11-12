// Animated film grain (fragment shader).
// Uniforms: t_scene, u_grain (0..1), u_time (seconds), u_tension (0..1)
// Uses a hash-based value noise that changes over time, avoiding any
// visible repetition (matches the NumPy tile-rotation fallback).
precision mediump float;
uniform sampler2D t_scene;
uniform float u_grain;
uniform float u_time;
uniform float u_tension;
varying vec2 v_uv;

float hash(vec2 p) {
    p = fract(p * 0.3183099 + 0.1);
    p = p * 217.7;
    return fract(p.x * p.y * (p.x + p.y));
}

void main() {
    vec3 c = texture2D(t_scene, v_uv).rgb;
    vec2 g = floor(v_uv * 960.0) + floor(u_time * 60.0); // animated cell
    float n = hash(g) - 0.5;
    float amount = (0.02 + 0.035 * u_tension) * u_grain;
    c += n * amount;
    gl_FragColor = vec4(c, 1.0);
}
