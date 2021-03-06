import numpy as np
import base64
import json
import vispy
from functools import partial
from vispy import gloo
from vispy.gloo import gl

gl_type_list = (
    'GL_FLOAT',
    'GL_FLOAT_VEC2',
    'GL_FLOAT_VEC3',
    'GL_FLOAT_VEC4',
    'GL_INT',
    'GL_INT_VEC2',
    'GL_INT_VEC3',
    'GL_INT_VEC4',
    'GL_BOOL',
    'GL_BOOL_VEC2',
    'GL_BOOL_VEC3',
    'GL_BOOL_VEC4',
    'GL_FLOAT_MAT2',
    'GL_FLOAT_MAT3',
    'GL_FLOAT_MAT4',
    'GL_SAMPLER_2D',
)
gl_typeinfo = {getattr(gl, t): t for t in gl_type_list}
gl_indexinfo = {
    np.dtype(np.uint8): 'GL_UNSIGNED_BYTE',
    np.dtype(np.uint16): 'GL_UNSIGNED_SHORT',
    np.dtype(np.uint32): 'GL_UNSIGNED_INT',
}

def _encode_data(data):
    return base64.b64encode(data)
        
def _decode_data(s, dtype):
    """Return a Numpy array from its encoded Base64 string. The dtype
    must be provided."""
    return np.fromstring(base64.b64decode(s), dtype=dtype)
        
def export_gtype(gtype):
    return gl_typeinfo[gtype]
        
def export_shader(shader):
    return shader.code
    
def export_data(data):
    if data is None:
        return None
    return {'dtype': data.dtype.descr,
            'buffer': _encode_data(data)}
    
def export_attribute(attr):
    return {'gtype': export_gtype(attr.gtype),
            'data': export_data(attr.data._data)}
    
def export_uniform(uni):
    return {'gtype': export_gtype(uni._gtype),
            'data': export_data(uni._data)}

def export_program(prog, mode=None, index=None):
    # TODO: separate data and objects
    # TODO: allow complex dtype by separating buffers and attributes
    # so that buffers can be shared between attributes
    attributes = {name: export_attribute(attr) 
                    for name, attr in prog._attributes.iteritems()}
    uniforms = {name: export_uniform(attr)
                    for name, attr in prog._uniforms.iteritems()}

    vs = export_shader(prog.shaders[0])
    fs = export_shader(prog.shaders[1])
    
    if index is not None:
        index = {
            'gtype': gl_indexinfo[index.data.dtype],
            'data': export_data(index.data)
            }
    
    d = {'attributes': attributes,
         'uniforms': uniforms,
         'index_buffer': index,
         'vertex_shader': vs,
         'fragment_shader': fs,
         'mode': mode,
         }
    return d

def find_programs(canvas):
    return [name for name in dir(canvas) 
        if isinstance(getattr(canvas, name), gloo.Program)]
    
def find_draw_info(canvas):
    """Find the primitive and indices passed to each program.draw(),
    using monkey patching."""
    info = {}
    def _f(p, mode=gl.GL_TRIANGLES, indices=None):
        info[p] = (mode, indices)
    programs = find_programs(canvas)
    _on_draw = []
    for p in programs:
        _on_draw.append(getattr(canvas, p).draw)
        setattr(getattr(canvas, p), 'draw', partial(_f, p))
    canvas.on_draw(None)
    for p, draw in zip(programs, _on_draw):
        setattr(getattr(canvas, p), 'draw', draw)
    return info
    
def export_canvas(canvas):
    programs = find_programs(canvas)
    draw_info = find_draw_info(canvas)
    return {'programs': {p: export_program(getattr(canvas, p), 
                                mode=draw_info[p][0],
                                index=draw_info[p][1],)
                            for p in programs}}
        
def export_canvas_json(canvas, filename):
    with open(filename, 'w') as f:
        f.write(json.dumps(export_canvas(canvas), indent=1))