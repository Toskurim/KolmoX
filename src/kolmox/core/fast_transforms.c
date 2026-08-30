#define PY_SSIZET_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

/* Fast 4-way Byte-Plane Transpose (Float32/Int32) */
static PyObject* fast_transpose_f32(PyObject* self, PyObject* args) {
    Py_buffer view;
    if (!PyArg_ParseTuple(args, "y*", &view)) return NULL;
    
    Py_ssize_t num_bytes = view.len;
    Py_ssize_t n = num_bytes / 4;
    PyObject* output = PyBytes_FromAndSize(NULL, num_bytes);
    if (!output) {
        PyBuffer_Release(&view);
        return NULL;
    }
    
    const uint8_t* src = (const uint8_t*)view.buf;
    uint8_t* dst = (uint8_t*)PyBytes_AS_STRING(output);
    uint8_t* p0 = dst;
    uint8_t* p1 = dst + n;
    uint8_t* p2 = dst + (2 * n);
    uint8_t* p3 = dst + (3 * n);
    
    for (Py_ssize_t i = 0; i < n; ++i) {
        p0[i] = src[4 * i];
        p1[i] = src[4 * i + 1];
        p2[i] = src[4 * i + 2];
        p3[i] = src[4 * i + 3];
    }
    
    PyBuffer_Release(&view);
    return output;
}

/* Fast Inverse 4-way Byte-Plane Transpose */
static PyObject* fast_untranspose_f32(PyObject* self, PyObject* args) {
    Py_buffer view;
    if (!PyArg_ParseTuple(args, "y*", &view)) return NULL;
    
    Py_ssize_t num_bytes = view.len;
    Py_ssize_t n = num_bytes / 4;
    PyObject* output = PyBytes_FromAndSize(NULL, num_bytes);
    if (!output) {
        PyBuffer_Release(&view);
        return NULL;
    }
    
    const uint8_t* src = (const uint8_t*)view.buf;
    uint8_t* dst = (uint8_t*)PyBytes_AS_STRING(output);
    const uint8_t* p0 = src;
    const uint8_t* p1 = src + n;
    const uint8_t* p2 = src + (2 * n);
    const uint8_t* p3 = src + (3 * n);
    
    for (Py_ssize_t i = 0; i < n; ++i) {
        dst[4 * i]     = p0[i];
        dst[4 * i + 1] = p1[i];
        dst[4 * i + 2] = p2[i];
        dst[4 * i + 3] = p3[i];
    }
    
    PyBuffer_Release(&view);
    return output;
}

static PyMethodDef FastMethods[] = {
    {"transpose_f32", fast_transpose_f32, METH_VARARGS, "Fast 4-way byte-plane transpose."},
    {"untranspose_f32", fast_untranspose_f32, METH_VARARGS, "Fast 4-way byte-plane inverse."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef fast_module = {
    PyModuleDef_HEAD_INIT,
    "fast_transforms",
    "KolmoX C-Accelerated Kernels",
    -1,
    FastMethods
};

PyMODINIT_FUNC PyInit_fast_transforms(void) {
    return PyModule_Create(&fast_module);
}
