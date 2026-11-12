// Soft spotlight for the flashlight (fragment shader, screen-space cone).
// Uniforms: u_flash_pos (0..1), u_dir (normalised screen-space aim),
// u_length, u_spread (radians), u_falloff, u_flicker (0..1), u_intensity
// Drawn additively over the scene before the darkness pass so the beam
// looks volumetric-ish against the fog.
precision mediump float;
uniform vec2 u_flash_pos;
uniform vec2 u_dir;
uniform float u_length;
uniform float u_spread;
uniform float u_falloff;
uniform float u_flicker;
uniform float u_intensity;
varying vec2 v_uv;

void main() {
    vec2 d = v_uv - u_flash_pos;
    float along = dot(d, u_dir);
    float side = abs(dot(d, vec2(-u_dir.y, u_dir.x)));
    if (along < 0.0 || along > u_length) {
        gl_FragColor = vec4(0.0);
        return;
    }
    float half_spread = u_spread * (0.25 + 0.75 * along / u_length);
    float cone = clamp(1.0 - side / max(0.001, half_spread * u_length
                                        * 0.35), 0.0, 1.0);
    float fall = pow(1.0 - along / u_length, u_falloff);
    float a = cone * fall * u_flicker * u_intensity;
    gl_FragColor = vec4(vec3(1.0, 0.95, 0.8) * a, a);
}
