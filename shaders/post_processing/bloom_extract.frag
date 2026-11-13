// Bloom extraction pass (fragment shader).
// Rendered into the LOW-resolution glow FBO: the scene texture is
// 9-tap sampled (each tap ~ one low-res pixel worth of scene texels),
// thresholded and passed on.  The original scene is never blurred; only
// this extracted glow buffer is small.
// Uniforms: t_scene, u_res_low (low-res buffer size), u_threshold (0..1)
precision highp float;
uniform sampler2D t_scene;
uniform vec2 u_res_low;
uniform float u_threshold;
varying vec2 v_uv;

void main() {
    vec2 px = 1.0 / u_res_low;
    vec3 acc = texture2D(t_scene, v_uv).rgb;
    acc += texture2D(t_scene, v_uv + vec2( px.x, 0.0)).rgb;
    acc += texture2D(t_scene, v_uv + vec2(-px.x, 0.0)).rgb;
    acc += texture2D(t_scene, v_uv + vec2(0.0,  px.y)).rgb;
    acc += texture2D(t_scene, v_uv + vec2(0.0, -px.y)).rgb;
    acc += texture2D(t_scene, v_uv + vec2( px.x,  px.y)).rgb;
    acc += texture2D(t_scene, v_uv + vec2(-px.x,  px.y)).rgb;
    acc += texture2D(t_scene, v_uv + vec2( px.x, -px.y)).rgb;
    acc += texture2D(t_scene, v_uv + vec2(-px.x, -px.y)).rgb;
    acc /= 9.0;
    acc = max(acc - u_threshold, 0.0);
    gl_FragColor = vec4(acc, 1.0);
}
