// Cinematic horror color grade (fragment shader).
// Uniforms: t_scene (scene texture), u_grade (0..1 strength), u_lowhp (0..1)
// GLSL mirror of graphics/post_processing.py step 3 (NumPy LUT).
precision mediump float;
uniform sampler2D t_scene;
uniform float u_grade;
uniform float u_lowhp;
varying vec2 v_uv;

// cool shadows, warm highlights, crushed midtones (horror look)
vec3 grade(vec3 c) {
    vec3 lut = c;
    float w = pow(1.0 - c.g, 2.0);            // shadow weight
    lut.r = clamp(c.r * 1.02 + 0.008 - w * 0.02, 0.0, 1.0);
    lut.g = clamp(c.g * 0.98 + 0.004 - w * 0.008, 0.0, 1.0);
    lut.b = clamp(c.b * 1.05 + 0.016 + w * 0.024, 0.0, 1.0);
    float lum = dot(lut, vec3(0.299, 0.587, 0.114));
    lut = lut * 0.94 + lum * 0.06;            // gentle desaturation
    return mix(c, lut, u_grade);
}

void main() {
    vec3 c = texture2D(t_scene, v_uv).rgb;
    c = grade(c);
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(c, vec3(lum), u_lowhp * 0.35);    // low-HP desaturation
    gl_FragColor = vec4(c, 1.0);
}
