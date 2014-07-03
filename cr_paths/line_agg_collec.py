from vispy import gloo
from vispy import app
import os
import numpy as np
import math

from dash_atlas import DashAtlas
from transforms import orthographic

from plot import PlotCanvas, Visual, Function, ModularProgram, STTransform

join = { 'miter' : 0,
         'round' : 1,
         'bevel' : 2 }

caps = { ''             : 0,
         'none'         : 0,
         '.'            : 0,
         'round'        : 1,
         ')'            : 1,
         '('            : 1,
         'o'            : 1,
         'triangle in'  : 2,
         '<'            : 2,
         'triangle out' : 3,
         '>'            : 3,
         'square'       : 4,
         '='            : 4,
         'butt'         : 4,
         '|'            : 5 }
         
def bake(vtype, vertices, closed=False):
    """
    Bake a list of 2D vertices for rendering them as thick line. Each line
    segment must have its own vertices because of antialias (this means no
    vertex sharing between two adjacent line segments).
    """

    n = len(vertices)
    P = np.array(vertices).reshape(n,2).astype(float)

    dx,dy = P[0] - P[-1]
    d = np.sqrt(dx*dx+dy*dy)

    # If closed, make sure first vertex = last vertex (+/- epsilon=1e-10)
    if closed and d > 1e-10:
        P = np.append(P, P[0]).reshape(n+1,2)
        n+= 1

    V = np.zeros(len(P), dtype = vtype)
    V['a_position'] = P

    # Tangents & norms
    T = P[1:] - P[:-1]
    
    N = np.sqrt(T[:,0]**2 + T[:,1]**2)
    # T /= N.reshape(len(T),1)
    V['a_tangents'][+1:, :2] = T
    if closed: V['a_tangents'][0  , :2] = T[-1]
    else:      V['a_tangents'][0  , :2] = T[0]
    V['a_tangents'][:-1, 2:] = T
    if closed: V['a_tangents'][ -1, 2:] = T[0]
    else:      V['a_tangents'][ -1, 2:] = T[-1]

    # Angles
    T1 = V['a_tangents'][:,:2]
    T2 = V['a_tangents'][:,2:]
    A = np.arctan2( T1[:,0]*T2[:,1]-T1[:,1]*T2[:,0],
                    T1[:,0]*T2[:,0]+T1[:,1]*T2[:,1])
    V['a_angles'][:-1,0] = A[:-1] 
    V['a_angles'][:-1,1] = A[+1:]

    # Segment
    L = np.cumsum(N)
    V['a_segment'][+1:,0] = L
    V['a_segment'][:-1,1] = L
    #V['a_lengths'][:,2] = L[-1]

    # Step 1: A -- B -- C  =>  A -- B, B' -- C
    V = np.repeat(V,2,axis=0)[+1:-1]
    V['a_segment'][1:] = V['a_segment'][:-1] 
    V['a_angles'][1:] = V['a_angles'][:-1] 
    V['a_texcoord'][0::2] = -1
    V['a_texcoord'][1::2] = +1

    # Step 2: A -- B, B' -- C  -> A0/A1 -- B0/B1, B'0/B'1 -- C0/C1
    V = np.repeat(V,2,axis=0)
    V['a_texcoord'][0::2,1] = -1
    V['a_texcoord'][1::2,1] = +1

    I = np.resize( np.array([0,1,2,1,2,3], dtype=np.uint32), (n-1)*(2*3))
    I += np.repeat( 4*np.arange(n-1), 6)

    return V, I, L[-1]

vtype = np.dtype( [('a_position', 'f4', 2),
                    ('a_tangents', 'f4', 4),
                    ('a_segment',  'f4', 2),
                    ('a_angles',   'f4', 2),
                    ('a_texcoord', 'f4', 2),
                    ('length', 'f4', 1),
                    ('color', 'f4', 4),
                    ])

uniforms = dict(
    closed = False,
    # color = (0.,0.,0.,1),
    linewidth = 10.,
    antialias = 1.0,
    miter_limit = 4.0,
    u_scale = 300,
    dash_phase = 0.0,
    # length=length,
    
    )


###########


class LineCollection(object):
    def __init__(self, paths=None, style=None):
        
        self.da = DashAtlas()
        self._index = 0
        self._Vs = []
        self._Is = []
        self._Us = []
        
        
        if style is None:
            style = [{}]*len(paths)
            
        for vertices, s in zip(paths, style):
            self.add(vertices, **s)
            
        
    def add(self, vertices, dash_pattern='solid', 
            color=(0.,0.,0.,1.)):
            
        linecaps = ('round','round')
        dash_caps = ('round', 'round')
        linejoin = 'round'
        
        dash_index, dash_period = self.da[dash_pattern]
        
    
        V, I, length = bake(vtype, vertices)
        V['length'] = length * np.ones(len(V))
        V['color'] = np.tile(color, (len(V), 1))
        
        self._Vs.append(V)
        self._Is.append(I + self._index)
        
        self._Us.append(dict(
            dash_index=dash_index,
            dash_period=dash_period,
            linejoin    = join.get(linejoin, 'round'),
            
            linecaps    = (caps.get(linecaps[0], 'round'),
                           caps.get(linecaps[1], 'round')),
                           
            dash_caps   = (caps.get(dash_caps[0], 'round'),
                           caps.get(dash_caps[1], 'round'))
        ))
        
        self._index += len(V)
        
    
    def build_buffers(self):
        V = np.concatenate(self._Vs)
        I = np.concatenate(self._Is)
        return V, I, self._Us


VERTEX_SHADER = open('path2.vert', 'r').read()
FRAGMENT_SHADER = open('path.frag', 'r').read()

class LineAggVisual(Visual):
    VERTEX_SHADER = VERTEX_SHADER
    FRAGMENT_SHADER = FRAGMENT_SHADER
    
    def __init__(self, **kwargs):
        self._program = ModularProgram(self.VERTEX_SHADER, self.FRAGMENT_SHADER)
        self._collec = LineCollection(**kwargs)
        self._V, self._I, self._U = self._collec.build_buffers()
        self.index = gloo.IndexBuffer(self._I)
        
    def set_options(self):
        gloo.set_state(clear_color=(1, 1, 1, 1), blend=True, 
                       blend_func=('src_alpha', 'one_minus_src_alpha'))

    def resize(self, (width, height)):
        self.width, self.height = width, height

    def draw(self):
        self.set_options()
        
        # WARNING: THIS IS TERRIBLY INEFFICIENT BECAUSE ALL DATA
        # IS SENT ON GPU AT EVERY REFRESH!!!
        # We need to put this stuff at initialization time.
        self._program._create()
        self._program._build()  # attributes / uniforms are not available until program is built
        
        self._program.bind(gloo.VertexBuffer(self._V))
        for n, v in uniforms.iteritems():
            self._program[n] = v
            
        # WARNING/TODO: put the different sets of uniforms and put them in attributes instead
        for n, v in self._U[0].iteritems():
            self._program[n] = v
            
        self._program['tr_scale'] = self._parent.panzoom.scale[:2]
            
        self._program['u_dash_atlas'] = gloo.Texture2D(self._collec.da._data)
        width, height = self.width, self.height
        self._program['u_proj'] = orthographic( -width//2, width//2, 
                                                -height//2, height//2, -1, +1 )
        
        self._program.draw('triangles', indices=self.index)



if __name__ == '__main__':
    ax = PlotCanvas(size=(600,600))
    
    
    x = np.linspace(-1., 1., 1000)
    y = .25*np.sin(15*x)
    vertices1 = np.c_[x,y]
    vertices2 = np.c_[x,y+.25]

    
    ax.line = LineAggVisual(paths=[vertices1, vertices2], style=[
        dict(color=(1., 0., 0., 1.)),
        dict(color=(0., 1., 0., 1.)),
    ])
    ax.show()

