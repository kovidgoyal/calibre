/*
 * certgen.c
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <openssl/rand.h>
#ifdef _WIN32
/* See http://openssl.6102.n7.nabble.com/The-infamous-win32-X509-NAME-define-problem-td11794.html */
#undef X509_NAME
#endif
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <openssl/ssl.h>
#include <openssl/rsa.h>
#include <openssl/evp.h>
#include <openssl/err.h>
#include <openssl/conf.h>

static PyObject*
set_error_with_detail(const char *where, const char* detail) {
    char *suffix = NULL, buf[1024];
    unsigned long err = ERR_get_error();
    if (err == 0) {
        suffix = "OpenSSL error queue is empty";
    } else {
        ERR_error_string_n(err, buf, sizeof(buf));
        suffix = buf;
    }
    if (detail && detail[0]) return PyErr_Format(PyExc_ValueError, "Error calling: %s %s: %s", where, detail, suffix);
    return PyErr_Format(PyExc_ValueError, "Error calling: %s: %s", where, suffix);
}

static PyObject*
set_error(const char *where) {
    return set_error_with_detail(where, NULL);
}

static void free_rsa_keypair(PyObject *capsule) {
    EVP_PKEY *pkey= PyCapsule_GetPointer(capsule, NULL);
    EVP_PKEY_free(pkey);
}

#if OPENSSL_VERSION_NUMBER < 0x30000000L
static EVP_PKEY *
EVP_RSA_gen(int keysize) {
    EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_id(EVP_PKEY_RSA, NULL);
    if (!ctx) return NULL;
    if (EVP_PKEY_keygen_init(ctx) <= 0) { EVP_PKEY_CTX_free(ctx); return NULL; }
    if (EVP_PKEY_CTX_set_rsa_keygen_bits(ctx, keysize) <= 0) {
        EVP_PKEY_CTX_free(ctx);
        return NULL;
    }
    EVP_PKEY *key = NULL;
    if (EVP_PKEY_keygen(ctx, &key) <= 0) {
        EVP_PKEY_CTX_free(ctx);
        return NULL;
    }
    EVP_PKEY_CTX_free(ctx);
    return key;
}
#endif

static PyObject*
create_rsa_keypair(PyObject *self, PyObject *args) {
    int keysize = 0;
    PyObject *ans = NULL;
    if(!PyArg_ParseTuple(args, "i", &keysize)) return NULL;
    if (keysize < 1024) return PyErr_Format(PyExc_ValueError, "The key size %d is less than 1024. 1024 is the minimum.", keysize);
    if (RAND_status() != 1) return PyErr_Format(PyExc_RuntimeError, "The OopenSSL PRNG failed to seed itself");

    EVP_PKEY *pkey;
    Py_BEGIN_ALLOW_THREADS;
    pkey = EVP_RSA_gen(keysize);
    Py_END_ALLOW_THREADS;
    if (pkey == NULL) return set_error("EVP_RSA_gen");
    ans = PyCapsule_New(pkey, NULL, free_rsa_keypair);
    return ans;
}

#ifdef _WIN32
static int add_entry(X509_NAME *Name, const char *field, const char *bytes) {
#else
static inline int add_entry(X509_NAME *Name, const char *field, const char *bytes) {
#endif
    if (bytes && *bytes) {
        if (!X509_NAME_add_entry_by_txt(Name, field, MBSTRING_ASC, (const unsigned char*)bytes, -1, -1, 0)) { set_error("X509_NAME_add_entry_by_txt"); return 0; }
    }
    return 1;
}

static void free_req(PyObject *capsule) {
    X509_REQ *Cert = PyCapsule_GetPointer(capsule, NULL);
    if (Cert) X509_REQ_free(Cert);
}

static int
add_ext(STACK_OF(X509_EXTENSION) *sk, int nid, const char *value, char *item_type) {
  X509_EXTENSION *ex = X509V3_EXT_conf_nid(NULL, NULL, nid, value);
  if (!ex) { set_error_with_detail("X509V3_EXT_conf_nid", value); return 0;}
  if (!sk_X509_EXTENSION_push(sk, ex)) { set_error_with_detail("sk_X509_EXTENSION_push", item_type); return 0; }
  return 1;
}

static PyObject* create_rsa_cert_req(PyObject *self, PyObject *args) {
    PyObject *capsule = NULL, *ans = NULL, *t = NULL;
    X509_NAME *Name = NULL;
    char *common_name = NULL, *country = NULL, *state = NULL, *locality = NULL, *org = NULL, *org_unit = NULL, *email = NULL, *basic_constraints = NULL;
    X509_REQ *Cert = NULL;
    PyObject *alt_names = NULL;
    int ok = 0, signature_length = 0;
    Py_ssize_t i = 0;
    STACK_OF(X509_EXTENSION) *exts = NULL;

    if(!PyArg_ParseTuple(args, "OO!szzzzzzz", &capsule, &PyTuple_Type, &alt_names, &common_name, &country, &state, &locality, &org, &org_unit, &email, &basic_constraints)) return NULL;
    if(!PyCapsule_CheckExact(capsule)) return PyErr_Format(PyExc_TypeError, "The key is not a capsule object");
    EVP_PKEY *KeyPair = PyCapsule_GetPointer(capsule, NULL);
    if (!KeyPair) return PyErr_Format(PyExc_TypeError, "The key capsule is NULL");
    Cert = X509_REQ_new();
    if (!Cert) return set_error("X509_REQ_new");
    if (!X509_REQ_set_version(Cert, 1)) { set_error("X509_REQ_set_version"); goto error; }
    Name = X509_REQ_get_subject_name(Cert);
    if (!Name) { set_error("X509_REQ_get_subject_name"); goto error; }
    if (!add_entry(Name, "C", country)) goto error;
    if (!add_entry(Name, "ST", state)) goto error;
    if (!add_entry(Name, "L", locality)) goto error;
    if (!add_entry(Name, "O", org)) goto error;
    if (!add_entry(Name, "OU", org_unit)) goto error;
    if (!add_entry(Name, "emailAddress", email)) goto error;
    if (!add_entry(Name, "CN", common_name)) goto error;

    if (PyTuple_GET_SIZE(alt_names) > 0 || basic_constraints) {
        exts = sk_X509_EXTENSION_new_null();
        if (!exts) { set_error("sk_X509_EXTENSION_new_null"); goto error; }
        for (i = 0; i < PyTuple_GET_SIZE(alt_names); i++) {
            t = PyTuple_GET_ITEM(alt_names, i);
            if (!PyUnicode_Check(t)) {
                PyErr_SetString(PyExc_TypeError, "ALT names must be unicode objects"); goto error;
            }
            if (!add_ext(exts, NID_subject_alt_name, PyUnicode_AsUTF8(t), "alt_names")) goto error;
        }
        if (basic_constraints) {
            if(!add_ext(exts, NID_basic_constraints, basic_constraints, "basic_constraints")) goto error;
        }
        X509_REQ_add_extensions(Cert, exts);
        sk_X509_EXTENSION_pop_free(exts, X509_EXTENSION_free);
    }

    if (!X509_REQ_set_pubkey(Cert, KeyPair))  { set_error("X509_REQ_set_pubkey"); goto error; }
    Py_BEGIN_ALLOW_THREADS;
    signature_length = X509_REQ_sign(Cert, KeyPair, EVP_sha256());
    Py_END_ALLOW_THREADS;
    if (signature_length <= 0) { set_error("X509_REQ_sign"); goto error; }
    ans = PyCapsule_New(Cert, NULL, free_req);
    if (!ans) { goto error; }
    ok = 1;
error:
    if (!ok) {
        if (Cert) X509_REQ_free(Cert);
    }
    return ans;
}

static void free_cert(PyObject *capsule) {
    X509 *Cert = PyCapsule_GetPointer(capsule, NULL);
    if (Cert) X509_free(Cert);
}

/* Presently this just uses a random number, but a more appealing solution
 * is to switch to using a hash of certain key elements. Apparently Verisign do
 * something similar and it seems like a damned good idea. The suggested
 * fields to hash are
 * - subject
 * - notBefore
 * - not After
 * The reason for this function is to allow easier abstraction :-)
 */
static int
certificate_set_serial(X509 *cert) {
#define SERIAL_RAND_BITS 128
    int rv = 0;
    unsigned char random_bytes[SERIAL_RAND_BITS / 8];
    if (RAND_bytes(random_bytes, sizeof(random_bytes)) != 1) {
        set_error("RAND_bytes in certificate_set_serial");
        return 0;
    }
    BIGNUM *bn = NULL; ASN1_INTEGER *sno = NULL;
    sno = ASN1_INTEGER_new();
    if (!sno) {
        PyErr_NoMemory(); goto err;
    }
    bn = BN_bin2bn(random_bytes, sizeof(random_bytes), NULL);
    if (!bn) {
        PyErr_NoMemory(); goto err;
    }
    if ((sno = BN_to_ASN1_INTEGER(bn,sno)) == NULL) {
        set_error("BN_to_ASN1_INTEGER"); goto err;
    }
    if (X509_set_serialNumber(cert, sno) != 1) {
        set_error("X509_set_serialNumber"); goto err ;
    }
    rv = 1;
err:
    if (bn != NULL) BN_free(bn);
    if (sno != NULL) ASN1_INTEGER_free(sno);
    return rv;
}


static PyObject* create_rsa_cert(PyObject *self, PyObject *args) {
    PyObject *reqC = NULL, *CA_certC = NULL, *CA_keyC = NULL, *ans = NULL;
    X509_REQ *req = NULL;
    X509 *CA_cert = NULL, *Cert = NULL;
    X509_NAME *Name = NULL;
    EVP_PKEY *PubKey = NULL;
    int not_before = 0, expire = 1, req_is_for_CA_cert = 0, signature_length = 0, ok = 0, i = 0;
    X509V3_CTX ctx;
    STACK_OF(X509_EXTENSION) *exts = NULL;

    if(!PyArg_ParseTuple(args, "OOO|ii", &reqC, &CA_certC, &CA_keyC, &not_before, &expire)) return NULL;
    if(!PyCapsule_CheckExact(reqC)) return PyErr_Format(PyExc_TypeError, "The req is not a capsule object");
    req_is_for_CA_cert = (CA_certC == Py_None) ? 1 : 0;
    if (!req_is_for_CA_cert) {if(!PyCapsule_CheckExact(CA_certC)) return PyErr_Format(PyExc_TypeError, "The CA_cert is not a capsule object");}
    if(!PyCapsule_CheckExact(CA_keyC)) return PyErr_Format(PyExc_TypeError, "The CA_key is not a capsule object");
    req = PyCapsule_GetPointer(reqC, NULL);
    if (!reqC) PyErr_Format(PyExc_TypeError, "The req capsule is NULL");
    if (!req_is_for_CA_cert) {
        CA_cert = PyCapsule_GetPointer(CA_certC, NULL);
        if (!CA_cert) PyErr_Format(PyExc_TypeError, "The CA_cert capsule is NULL");
    }
    EVP_PKEY *CA_key = PyCapsule_GetPointer(CA_keyC, NULL);
    if (!CA_key) PyErr_Format(PyExc_TypeError, "The CA_key capsule is NULL");

    Cert = X509_new();
    if (!Cert) { set_error("X509_new"); goto error; }
    if (!X509_set_version (Cert, 2)) { set_error("X509_set_version"); goto error; }
    if (!certificate_set_serial(Cert)) goto error;
#ifdef X509_time_adj_ex
    if(!X509_time_adj_ex(X509_get_notBefore(Cert), not_before, 0, NULL)) { set_error("X509_time_adj_ex"); goto error; }
    if(!X509_time_adj_ex(X509_get_notAfter(Cert), expire, 0, NULL)) { set_error("X509_time_adj_ex"); goto error; }
#else
    if(!X509_gmtime_adj(X509_get_notBefore(Cert), not_before * 24 * 60 * 60)) { set_error("X509_gmtime_adj"); goto error; }
    if(!X509_gmtime_adj(X509_get_notAfter(Cert), expire * 24 * 60 * 60)) { set_error("X509_gmtime_adj"); goto error; }
#endif

    Name = X509_REQ_get_subject_name(req);
    if (!Name) { set_error("X509_REQ_get_subject_name(req)"); goto error; }
    if (!X509_set_subject_name(Cert, Name)) { set_error("X509_set_subject_name"); goto error; }

    if (req_is_for_CA_cert) Name = X509_REQ_get_subject_name((X509_REQ*)req);
    else Name = X509_get_subject_name(CA_cert);
    if (!Name) { set_error("X509_REQ_get_subject_name(CA_cert)"); goto error; }
    if (!X509_set_issuer_name(Cert, Name)) { set_error("X509_set_issuer_name"); goto error; }

    exts = X509_REQ_get_extensions(req);
    if (exts) {
        X509V3_set_ctx(&ctx, CA_cert, Cert, NULL, NULL, 0);
        for (i = 0; i < sk_X509_EXTENSION_num(exts); i++) {
            if(!X509_add_ext(Cert, sk_X509_EXTENSION_value(exts, i), -1)) { set_error("X509_add_ext"); goto error; }
        }
    }

    PubKey=X509_REQ_get_pubkey(req);
    if (!PubKey) { set_error("X509_REQ_get_pubkey"); goto error; }
    if (!X509_REQ_verify(req, PubKey)) { set_error("X509_REQ_verify"); goto error; }
    if (!X509_set_pubkey(Cert, PubKey)) { set_error("X509_set_pubkey"); goto error; }
    Py_BEGIN_ALLOW_THREADS;
    signature_length = X509_sign(Cert, CA_key, EVP_sha256());
    Py_END_ALLOW_THREADS;
    if (signature_length <= 0) { set_error("X509_sign"); goto error; }
    ans = PyCapsule_New(Cert, NULL, free_cert);
    if (!ans) { PyErr_NoMemory(); goto error; }
    ok = 1;

error:
    if (!ok) {
        if (Cert) X509_free(Cert);
    }
    return ans;
}

static PyObject* serialize_cert(PyObject *self, PyObject *args) {
    PyObject *capsule = NULL, *ans = NULL;
    X509 *cert = NULL;
    BIO *mem = NULL;
    long sz = 0;
    char *p = NULL;

    if(!PyArg_ParseTuple(args, "O", &capsule)) return NULL;
    if(!PyCapsule_CheckExact(capsule)) return PyErr_Format(PyExc_TypeError, "The cert is not a capsule object");
    cert = PyCapsule_GetPointer(capsule, NULL);
    if (!cert) return PyErr_Format(PyExc_TypeError, "The cert capsule is NULL");

    mem = BIO_new(BIO_s_mem());
    if (!mem) return set_error("BIO_new");
    if (!PEM_write_bio_X509(mem, cert)) { BIO_free(mem); return set_error("PEM_write_bio_X509"); }
    sz = BIO_get_mem_data(mem, &p);
    Py_ssize_t psz = sz;
    ans = Py_BuildValue("s#", p, psz);
    BIO_free(mem);
    return ans;
}

static PyObject* cert_info(PyObject *self, PyObject *args) {
    PyObject *capsule = NULL, *ans = NULL;
    X509 *cert = NULL;
    BIO *mem = NULL;
    long sz = 0;
    char *p = NULL;

    if(!PyArg_ParseTuple(args, "O", &capsule)) return NULL;
    if(!PyCapsule_CheckExact(capsule)) return PyErr_Format(PyExc_TypeError, "The cert is not a capsule object");
    cert = PyCapsule_GetPointer(capsule, NULL);
    if (!cert) return PyErr_Format(PyExc_TypeError, "The cert capsule is NULL");

    mem = BIO_new(BIO_s_mem());
    if (!mem) return set_error("BIO_new");
    if (!X509_print_ex(mem, cert, XN_FLAG_COMPAT, X509_FLAG_COMPAT)) { BIO_free(mem); return set_error("X509_print_ex"); }
    sz = BIO_get_mem_data(mem, &p);
    Py_ssize_t psz = sz;
    ans = Py_BuildValue("s#", p, psz);
    BIO_free(mem);
    return ans;
}

static PyObject* serialize_rsa_key(PyObject *self, PyObject *args) {
    PyObject *capsule = NULL, *ans = NULL;
    char *password = NULL;
    EVP_PKEY *keypair = NULL;
    BIO *mem = NULL;
    long sz = 0;
    int ok = 0;
    char *p = NULL;

    if(!PyArg_ParseTuple(args, "Oz", &capsule, &password)) return NULL;
    if(!PyCapsule_CheckExact(capsule)) return PyErr_Format(PyExc_TypeError, "The key is not a capsule object");
    keypair = PyCapsule_GetPointer(capsule, NULL);
    if (!keypair) return PyErr_Format(PyExc_TypeError, "The key capsule is NULL");

    mem = BIO_new(BIO_s_mem());
    if (!mem) {set_error("BIO_new"); goto error; }
    if (password && *password) ok = PEM_write_bio_PrivateKey(mem, keypair, EVP_des_ede3_cbc(), NULL, 0, 0, password);
    else ok = PEM_write_bio_PrivateKey(mem, keypair, NULL, NULL, 0, 0, NULL);
    if (!ok) { set_error("PEM_write_bio_PrivateKey"); goto error; }
    sz = BIO_get_mem_data(mem, &p);
    Py_ssize_t psz = sz;
    ans = Py_BuildValue("s#", p, psz);
error:
    if (mem) BIO_free(mem);
    return ans;
}

static PyMethodDef certgen_methods[] = {
    {"create_rsa_keypair", create_rsa_keypair, METH_VARARGS,
        "create_rsa_keypair(size)\n\nCreate a RSA keypair of the specified size"
    },

    {"create_rsa_cert_req", create_rsa_cert_req, METH_VARARGS,
        "create_rsa_cert_req(keypair, alt_names, common_name, country, state, locality, org, org_unit, email_address)\n\nCreate a certificate signing request."
    },

    {"create_rsa_cert", create_rsa_cert, METH_VARARGS,
        "create_rsa_cert(req, CA_cert, CA_key, not_before, expire)\n\nCreate a certificate from a signing request."
    },

    {"serialize_cert", serialize_cert, METH_VARARGS,
        "serialize_cert(cert)\n\nReturn certificate as a PEM format bytestring"
    },

    {"serialize_rsa_key", serialize_rsa_key, METH_VARARGS,
        "serialize_rsa_key(key, [password])\n\nReturn key as a PEM format bytestring, optionally encrypted by password"
    },

    {"cert_info", cert_info, METH_VARARGS,
        "cert_info(cert)\n\nReturn the certificate information (certificate in text format)"
    },

    {NULL, NULL, 0, NULL}
};


static int
exec_module(PyObject *module) {
    OpenSSL_add_all_algorithms();
    ERR_load_crypto_strings();
	return 0;
}
static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "certgen",
    .m_doc      = "OpenSSL bindings to easily create certificates/certificate authorities.",
    .m_methods  = certgen_methods,
    .m_slots    = slots,

};

CALIBRE_MODINIT_FUNC PyInit_certgen(void) { return PyModuleDef_Init(&module_def); }
