// HDR-style bloom approximation (fragment shader).
// Pipeline (CPU-driven): threshold+downsample pass -> blur pass ->
// composite. This shader implements the composite; the NumPy fallback in
// graphics/post_processing.py implements the full chain at fx_res.
// Uniforms: t_scene, t_bloom (blurred thresholded brights), u_strength,
// u_threshold (0..255/255)
precision mediump float;
uniform sampler2D t_scene;
uniform sampler2D t_bloom;
uniform float u_strength;
uniform float u_threshold;
varying vec2 v_uv;

void main() {
    vec3 c = texture2D(t_scene, v_uv).rgb;
    vec3 b = texture2D(t_bloom, v_uv).rgb;
    float br = max(max(b.r, b.g), b.b);
    b = b * max(0.0, br - u_threshold) * 1.4;   // soft knee
    gl_FragColor = vec4(c + b * u_strength, 1.0);
}
