// Subtle chromatic aberration (fragment shader).
// Uniforms: t_scene, u_ca (0..1, eased by the CPU), u_tension
// The offset grows toward the screen edges (r^2 weighting) so the
// centre of the screen stays clean and gameplay remains readable.
precision mediump float;
uniform sampler2D t_scene;
uniform float u_ca;
uniform float u_tension;
varying vec2 v_uv;

void main() {
    vec2 p = v_uv * 2.0 - 1.0;
    float r2 = dot(p, p);
    float off = (0.0015 + 0.004 * u_ca + 0.001 * u_tension) * r2;
    vec2 dir = normalize(p + 1e-6);
    vec3 c;
    c.r = texture2D(t_scene, v_uv + dir * off).r;
    c.g = texture2D(t_scene, v_uv).g;
    c.b = texture2D(t_scene, v_uv - dir * off).b;
    gl_FragColor = vec4(c, 1.0);
}
