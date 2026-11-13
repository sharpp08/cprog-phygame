// Subtle heat-warp / supernatural spatial distortion (fragment shader).
// Uniforms: t_scene, u_amount (0..1 eased), u_time
// Low-amplitude sinusoidal warp; a radial ripple near the screen centre
// makes events feel "supernatural" rather than heat-like alone.
precision mediump float;
uniform sampler2D t_scene;
uniform float u_amount;
uniform float u_time;
varying vec2 v_uv;

void main() {
    if (u_amount < 0.02) {
        gl_FragColor = texture2D(t_scene, v_uv);
        return;
    }
    float a = u_amount * 0.004;
    vec2 p = v_uv - 0.5;
    float d = length(p);
    vec2 warp = vec2(sin(v_uv.y * 11.0 + u_time * 2.1),
                     cos(v_uv.x * 13.0 - u_time * 1.7)) * a;
    warp += normalize(p + 1e-6) * sin(d * 14.0 - u_time * 3.0) * a * 0.5;
    gl_FragColor = texture2D(t_scene, v_uv + warp);
}
