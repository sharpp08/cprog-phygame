"""Ad-hoc check that a live ModernGL texture/FBO/readback chain works."""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame
import moderngl

W, H = 1280, 720
pygame.init()
pygame.display.set_mode((W, H))
src = pygame.Surface((W, H))
src.fill((40, 50, 45))
pygame.draw.line(src, (255, 255, 255), (0, 100), (W, 100), 1)

t0 = time.perf_counter()
ctx = moderngl.create_standalone_context()
print("context: %.2f ms" % ((time.perf_counter() - t0) * 1000))

vsrc = "attribute vec2 a_pos; varying vec2 v_uv; void main(){ v_uv=a_pos*0.5+0.5; gl_Position=vec4(a_pos,0.0,1.0); }"
fsrc = """
precision highp float;
uniform sampler2D t;
varying vec2 v_uv;
void main(){ gl_FragColor = vec4(texture2D(t, v_uv).rgb, 1.0); }
"""
prog = ctx.program(vertex_shader=vsrc, fragment_shader=fsrc)
buf = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], dtype="float32").tobytes())
vao = ctx.vertex_array(prog, [(buf, "1f", "a_pos")], mode=moderngl.TRIANGLES)

tex = ctx.texture((W, H), 4)
fbo = ctx.framebuffer(color_attachments=tex)


def run(n=60):
    tex.write(pygame.image.tobytes(src, "RGBA"))
    fbo.use()
    vao.render()
    data = tex.read()
    arr = np.frombuffer(data, np.uint8).reshape(H, W, 4)
    out = np.ascontiguousarray(arr[..., :3].transpose(1, 0, 2))
    pygame.surfarray.blit_array(src, out)


run(3)
N = 120
import time as _t


def time1(fn, n=N):
    for _ in range(10):
        fn()
    t0 = _t.perf_counter()
    for _ in range(n):
        fn()
    return (_t.perf_counter() - t0) / n * 1000


f0 = time1(lambda: pygame.image.tobytes(src, "RGBA"))
f1 = time1(lambda: tex.write(pygame.image.tobytes(src, "RGBA")))
f2 = time1(lambda: (fbo.use(), vao.render()))
f3 = time1(lambda: tex.read())
f4 = time1(lambda: np.frombuffer(b"1" * (H * W * 4), np.uint8))
print("tobytes       : %.2f ms" % f0)
print("write(+bytes) : %.2f ms" % f1)
print("fbo render    : %.2f ms" % f2)
print("tex.read      : %.2f ms" % f3)
ctx.release()

