import sys, struct, pickle, socket
import numpy as np
import OpenGL.GL as gl
import OpenGL.GLUT as glut

from vispy.gloo import Program, VertexBuffer, IndexBuffer
from vispy.util.transforms import perspective, translate, rotate
from vispy.util.cube import cube
from vispy.gloo import gl


vertex = """
uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;
attribute vec3 position;
attribute vec4 color;
varying vec4 v_color;
void main()
{
    v_color = color;
    gl_Position = projection * view * model * vec4(position,1.0);
}
"""

fragment = """
varying vec4 v_color;
void main()
{
    gl_FragColor = v_color;
}
"""

PORT = 8090
HOST = "localhost"
sock = socket.socket()
sock.connect((HOST,PORT))

def send_msg(socket, msg):
    temp = ""
    length = len(msg)

    for i in range(0, length, 2**16):
        if i+2**16 > length:
            temp = msg[i:]
        else:
            temp = msg[i:i+2**16]

        temp = struct.pack('>I', len(temp)) + temp
        socket.send(temp)

def display():
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    program.draw(gl.GL_TRIANGLES, indices)
    glut.glutSwapBuffers()

    # I think sending the message after each display is appropriate
    # However I am not sure.
    send_msg(sock, toPNG())


def toPNG():
    shot = screenshot()
    msg = pickle.dumps(shot)
    return msg


def screenshot(viewport=None):
    """ Take a screenshot using glReadPixels. Not sure where to put this
    yet, so a private function for now. Used in make.py.
    """
    # gl.glReadBuffer(gl.GL_BACK) Not avaliable in ES 2.0
    if viewport is None:
        viewport = gl.glGetParameter(gl.GL_VIEWPORT)
    x, y, w, h = 0, 0, 500, 500
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1) # PACK, not UNPACK
    im = gl.glReadPixels(x, y, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 4)

    # reshape, flip, and return
    if not isinstance(im, np.ndarray):
        im = np.frombuffer(im, np.uint8)
    im.shape = h, w, 3
    im = np.flipud(im)
    return im


def reshape(width, height):
    gl.glViewport(0, 0, width, height)
    projection = perspective(45.0, width / float(height), 2.0, 10.0)
    program['projection'] = projection


def keyboard(key, x, y):
    if key == '\033':
        sys.exit()


def timer(fps):
    global theta, phi
    theta += .5
    phi += .5
    model = np.eye(4, dtype=np.float32)
    rotate(model, theta, 0, 0, 1)
    rotate(model, phi, 0, 1, 0)
    program['model'] = model
    glut.glutTimerFunc(1000 / fps, timer, fps)
    glut.glutPostRedisplay()


# Glut init
# --------------------------------------
glut.glutInit(sys.argv)
glut.glutInitDisplayMode(glut.GLUT_DOUBLE | glut.GLUT_RGBA | glut.GLUT_DEPTH)
glut.glutCreateWindow('Colored Cube')
glut.glutReshapeWindow(512, 512)
glut.glutReshapeFunc(reshape)
glut.glutKeyboardFunc(keyboard)
glut.glutDisplayFunc(display)
glut.glutTimerFunc(1000 / 60, timer, 60)

# Build cube data
# --------------------------------------
V, I, _ = cube()
vertices = VertexBuffer(V)
indices = IndexBuffer(I)

# Build program
# --------------------------------------
program = Program(vertex, fragment)
program.bind(vertices)

# Build view, model, projection & normal
# --------------------------------------
view = np.eye(4, dtype=np.float32)
model = np.eye(4, dtype=np.float32)
projection = np.eye(4, dtype=np.float32)
translate(view, 0, 0, -5)
program['model'] = model
program['view'] = view
phi, theta = 0, 0

# OpenGL initalization
# --------------------------------------
gl.glClearColor(0.30, 0.30, 0.35, 1.00)
gl.glEnable(gl.GL_DEPTH_TEST)

# Start
# --------------------------------------
glut.glutMainLoop()
