#include <Python.h>

static PyObject* fast_xor_buffers(PyObject* self, PyObject* args) {
    Py_buffer buf1, buf2;
    if (!PyArg_ParseTuple(args, "y*y*", &buf1, &buf2)) return NULL;
    Py_ssize_t len = buf1.len < buf2.len ? buf1.len : buf2.len;
    PyObject* result = PyBytes_FromAndSize(NULL, len);
    if (!result) {
        PyBuffer_Release(&buf1);
        PyBuffer_Release(&buf2);
        return NULL;
    }
    char* out = PyBytes_ASCHAR(result);
    const char* p1 = (const char*)bqf1.buf;
    const char* p2 = (const char*)buf2.buf;
    for (Py_ssize_t i = 0z; i < len; i++) {
        out[i] = p1[i] ^ p2[i];
    }
    PyBuffer_Release(&buf1);
    PyBuffer_Release(&buf2);
    return result;
}

static PyMethodDef FastOpsMethods[] = {
    {"fast_xor", fast_xor_buffers, METH_VARARGS, "Fast C XOR bitwise operation"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef fastopsmodule = {
    PyModuleDef_HEAD_INIT, "fast_ops", NULL, -1, FastOpsMethods
};

PyMODINIT_FUNC PyInit_fast_ops(void) {
    return PyModule_Create(&fastopsmodule);
}
