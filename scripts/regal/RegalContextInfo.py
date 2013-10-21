#!/usr/bin/python -B

from string import Template, upper, replace

from ApiUtil import outputCode

cond = { 'wgl' : 'REGAL_SYS_WGL', 'glx' : 'REGAL_SYS_GLX', 'cgl' : 'REGAL_SYS_OSX', 'egl' : 'REGAL_SYS_EGL' }

contextInfoHeaderTemplate = Template( '''${AUTOGENERATED}
${LICENSE}

#ifndef __${HEADER_NAME}_H__
#define __${HEADER_NAME}_H__

#include "RegalUtil.h"

REGAL_GLOBAL_BEGIN

#include <GL/Regal.h>

#include <set>
#include <string>

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

struct RegalContext;

struct ContextInfo
{
  ContextInfo();
  ~ContextInfo();

  void init(const RegalContext &context);

  // glewGetExtension

  bool getExtension(const char *ext) const;

  // As reported by OpenGL implementation

  std::string vendor;
  std::string renderer;
  std::string version;
  std::string extensions;

  //

  std::set<std::string> extensionsSet;

  // As supported by the OpenGL implementation

${VERSION_DECLARE}

  // Driver context limits

${IMPL_DECLARE}

private:
  static bool stringSetFind(const std::set<std::string> &stringSet, const std::string &val);
};

REGAL_NAMESPACE_END

#endif // __${HEADER_NAME}_H__
''')

contextInfoSourceTemplate = Template( '''${AUTOGENERATED}
${LICENSE}

#include "pch.h" /* For MS precompiled header support */

#include "RegalUtil.h"

REGAL_GLOBAL_BEGIN

#include <GL/Regal.h>

#include <string>
#include <set>
using namespace std;

#include <boost/print/string_list.hpp>
using namespace boost::print;

#include "RegalEmu.h"
#include "RegalToken.h"
#include "RegalContext.h"
#include "RegalContextInfo.h"

REGAL_GLOBAL_END

REGAL_NAMESPACE_BEGIN

using namespace ::REGAL_NAMESPACE_INTERNAL::Logging;
using namespace ::REGAL_NAMESPACE_INTERNAL::Token;

ContextInfo::ContextInfo()
:
${VERSION_INIT}
${IMPL_INIT}
{
   Internal("ContextInfo::ContextInfo","()");
}

ContextInfo::~ContextInfo()
{
   Internal("ContextInfo::~ContextInfo","()");
}

inline string getString(const RegalContext &context, const GLenum e)
{
  Internal("getString ",toString(e));
  RegalAssert(context.dispatcher.driver.glGetString);
  const GLubyte *str = context.dispatcher.driver.glGetString(e);
  return str ? string(reinterpret_cast<const char *>(str)) : string();
}

inline void warnGLError(const RegalContext &context, const char *message)
{
  Internal("warnGLError ",message ? message : NULL);
  RegalAssert(context.dispatcher.driver.glGetError);
  GLenum err = context.dispatcher.driver.glGetError();
  if (err!=GL_NO_ERROR)
    Warning("glGetError returned ",GLerrorToString(err)," ",message ? message : NULL);
}

void
ContextInfo::init(const RegalContext &context)
{
  warnGLError(context,"before Regal context initialization.");

  // OpenGL Version.

  vendor     = getString(context, GL_VENDOR);
  renderer   = getString(context, GL_RENDERER);
  version    = getString(context, GL_VERSION);

  Info("OpenGL vendor    : ",vendor);
  Info("OpenGL renderer  : ",renderer);
  Info("OpenGL version   : ",version);

  gl_version_major = 0;
  gl_version_minor = 0;

  gles_version_major = 0;
  gles_version_minor = 0;

  // Detect GL context version
  //
  // Note: We need to detect desktop ES contexts even if REGAL_SYS_ES1 or REGAL_SYS_ES2
  //       are disabled.

  es1 = starts_with(version, "OpenGL ES-CM");
  if (es1)
  {
    sscanf(version.c_str(), "OpenGL ES-CM %d.%d", &gles_version_major, &gles_version_minor);
  }
  else
  {
    es2 = starts_with(version,"OpenGL ES ");
    if (es2)
    {
      sscanf(version.c_str(), "OpenGL ES %d.%d", &gles_version_major, &gles_version_minor);
    }
    else
    {
      sscanf(version.c_str(), "%d.%d", &gl_version_major, &gl_version_minor);
    }
  }

  // We could get either form of the OpenGL ES string, so confirm version

  #if REGAL_SYS_ES1 || REGAL_SYS_ES2
  if (!es1 && (gles_version_major == 1))
  {
    es1 = GL_TRUE;
    es2 = GL_FALSE;
  }
  else if (!es2 && (gles_version_major == 2))
  {
    es1 = GL_FALSE;
    es2 = GL_TRUE;
  }
  #endif

  #if REGAL_SYS_EMSCRIPTEN
  webgl = starts_with(version, "WebGL");
  #endif

  // For Mesa3D EGL/ES 2.0 on desktop Linux the version string doesn't start with
  // "OpenGL ES" Is that a Mesa3D bug? Perhaps...

  #if REGAL_SYS_ES2 && REGAL_SYS_EGL && !REGAL_SYS_ANDROID && !REGAL_SYS_EMSCRIPTEN
  if (Regal::Config::sysEGL)
  {
    es1 = false;
    es2 = true;
    webgl = false;
    gles_version_major = 2;
    gles_version_minor = 0;
  }
  #endif

  #if REGAL_SYS_ES2 && REGAL_SYS_EGL && REGAL_SYS_EMSCRIPTEN
  {
    es1 = false;
    es2 = true;
    webgl = true;
    gles_version_major = 2;
    gles_version_minor = 0;
  }
  #endif

  // Detect core context for GL 3.2 onwards

  if (!es1 && !es2 && (gl_version_major>3 || (gl_version_major==3 && gl_version_minor>=2)))
  {
    GLint flags = 0;
    RegalAssert(context.dispatcher.driver.glGetIntegerv);
    context.dispatcher.driver.glGetIntegerv(GL_CONTEXT_PROFILE_MASK, &flags);
    core = flags & GL_CONTEXT_CORE_PROFILE_BIT ? GL_TRUE : GL_FALSE;
  }

  compat = !core && !es1 && !es2 && !webgl;

  if (REGAL_FORCE_CORE_PROFILE || Config::forceCoreProfile)
  {
    compat = false;
    core   = true;
    es1    = false;
    es2    = false;
  }

  #if REGAL_SYS_ES1
  if (REGAL_FORCE_ES1_PROFILE || Config::forceES1Profile)
  {
    compat = false;
    core   = false;
    es1    = true;
    es2    = false;
  }
  #endif

  #if REGAL_SYS_ES2
  if (REGAL_FORCE_ES2_PROFILE || Config::forceES2Profile)
  {
    compat = false;
    core   = false;
    es1    = false;
    es2    = true;
  }
  #endif

  // Detect driver extensions

  string_list<string> driverExtensions;

  if (core)
  {
    RegalAssert(context.dispatcher.driver.glGetStringi);
    RegalAssert(context.dispatcher.driver.glGetIntegerv);

    GLint n = 0;
    context.dispatcher.driver.glGetIntegerv(GL_NUM_EXTENSIONS, &n);

    for (GLint i=0; i<n; ++i)
      driverExtensions.push_back(reinterpret_cast<const char *>(context.dispatcher.driver.glGetStringi(GL_EXTENSIONS,i)));
    extensions = driverExtensions.join(" ");
  }
  else
  {
    extensions = getString(context, GL_EXTENSIONS);
    driverExtensions.split(extensions,' ');
  }

  extensionsSet.insert(driverExtensions.begin(),driverExtensions.end());

  Info("OpenGL extensions: ",extensions);

${VERSION_DETECT}

  // Driver extensions, etc detected by Regal

  set<string> e;
  e.insert(driverExtensions.begin(),driverExtensions.end());

${EXT_INIT}

  RegalAssert(context.dispatcher.driver.glGetIntegerv);
  RegalAssert(context.dispatcher.driver.glGetBooleanv);
${IMPL_GET}

  Info("OpenGL v attribs : ",gl_max_vertex_attribs);
  Info("OpenGL varyings  : ",gl_max_varying_floats);

  warnGLError(context,"querying context information.");
}

bool
ContextInfo::stringSetFind(const std::set<std::string> &stringSet, const std::string &val)
{
  return stringSet.find(val)!=stringSet.end();
}

${EXT_CODE}

REGAL_NAMESPACE_END
''')

def traverseContextInfo(apis, args):

  for api in apis:
    if api.name == 'gles':
      api.versions =  [ [2, 0] ]
    if api.name == 'gl':
      api.versions =  [ [4,4], [4,3], [4,2], [4, 1], [4, 0] ]
      api.versions += [ [3, 3], [3, 2], [3, 1], [3, 0] ]
      api.versions += [ [2, 1], [2, 0] ]
      api.versions += [ [1, 5], [1, 4], [1, 3], [1, 2], [1, 1], [1, 0] ]
    if api.name == 'glx':
      api.versions = [ [1, 4], [1, 3], [1, 2], [1, 1], [1, 0] ]
    if api.name == 'egl':
      api.versions = [ [1, 2], [1, 1], [1, 0] ]
    c = set()
    c.update([i.category for i in api.functions])
    c.update([i.category for i in api.typedefs])
    c.update([i.category for i in api.enums])
    c.update([i.category for i in api.extensions])

    for i in api.enums:
      c.update([j.category for j in i.enumerants])

    api.categories = [i for i in c if i and len(i) and i.find('_VERSION_')==-1 and i.find('WGL_core')==-1]

    if api.name == 'egl':
      api.categories = [i for i in api.categories if not i.startswith('GL_')]

def versionDeclareCode(apis, args):

  code = ''
  for api in apis:
    name = api.name.lower()

    if name == 'gl':
      code += '  GLboolean compat : 1;\n'
      code += '  GLboolean core   : 1;\n'
      code += '  GLboolean es1    : 1;\n'
      code += '  GLboolean es2    : 1;\n'
      code += '  GLboolean webgl  : 1;\n\n'

    if name in ['gl', 'glx', 'egl']:
      code += '  GLint     %s_version_major;\n' % name
      code += '  GLint     %s_version_minor;\n' % name
      code += '\n'

    if hasattr(api, 'versions'):
      for version in sorted(api.versions):
        code += '  GLboolean %s_version_%d_%d : 1;\n' % (name, version[0], version[1])
      code += '\n'

    if name == 'gl':
      code += '  GLint     gles_version_major;\n'
      code += '  GLint     gles_version_minor;\n'
      code += '\n'
      code += '  GLint     glsl_version_major;\n'
      code += '  GLint     glsl_version_minor;\n'
      code += '\n'

  for api in apis:
    name = api.name.lower()
    if name in cond:
      code += '#if %s\n'%cond[name]
    for c in sorted(api.categories):
      code += '  GLboolean %s : 1;\n' % (c.lower())
    if name in cond:
      code += '#endif\n'
    code += '\n'

  return code

def versionInitCode(apis, args):

  code = ''
  for api in apis:
    name = api.name.lower()

    if name == 'gl':
      code += '  compat(false),\n'
      code += '  core(false),\n'
      code += '  es1(false),\n'
      code += '  es2(false),\n'
      code += '  webgl(false),\n'

    if name in ['gl', 'glx', 'egl']:
      code += '  %s_version_major(-1),\n' % name
      code += '  %s_version_minor(-1),\n' % name

    if hasattr(api, 'versions'):
      for version in sorted(api.versions):
        code += '  %s_version_%d_%d(false),\n' % (name, version[0], version[1])

    if name == 'gl':
      code += '  gles_version_major(-1),\n'
      code += '  gles_version_minor(-1),\n'
      code += '  glsl_version_major(-1),\n'
      code += '  glsl_version_minor(-1),\n'

  for api in apis:
    name = api.name.lower()
    if name in cond:
      code += '#if %s\n'%cond[name]
    for c in sorted(api.categories):
      code += '  %s(false),\n' % (c.lower())
    if name in cond:
      code += '#endif\n'

  return code

def versionDetectCode(apis, args):

  code = ''

  for api in apis:
    name = api.name.lower()
    if not hasattr(api, 'versions'):
      continue

    indent = ''
    if api.name=='gl':
      indent = '  '
      code += '  if (!es1 && !es2)\n  {\n'

    for i in range(len(api.versions)):
      version = api.versions[i]
      versionMajor = version[0]
      versionMinor = version[1]

      # Latest version

      if i is 0:
        code += '%s  %s_version_%d_%d = '%(indent, name, versionMajor, versionMinor)
        if versionMinor > 0:
          code += '%s_version_major > %d || (%s_version_major == %d && %s_version_minor >= %d);\n' % (name, versionMajor, name, versionMajor, name, versionMinor)
        else:
          code += '%s_version_major >= %d;\n' % (name, versionMajor)
        continue

      versionLast = api.versions[i-1]

      code += '%s  %s_version_%d_%d = %s_version_%d_%d || '%(indent,name,versionMajor,versionMinor,name,versionLast[0],versionLast[1])
      if versionMinor > 0:
        code += '(%s_version_major == %d && %s_version_minor == %d);\n' % (name, versionMajor, name, versionMinor)
      else:
        code += '%s_version_major == %d;\n' % (name, versionMajor)

    if len(indent):
      code += '  }\n'

    code += '\n'

  return code

def implDeclareCode(apis, args):

  code = ''
  for api in apis:
    name = api.name.lower()

    if name == 'gl':
      code += '\n'

      states = []
      for state in api.states:
        states.append(state.getValue.lower())

      for state in sorted(states):
        code += '  GLuint gl_%s;\n' % (state)

      code += '\n'
      code += '  GLuint gl_max_varying_floats;\n'
      code += '\n'
      code += '  GLboolean gl_quads_follow_provoking_vertex_convention;\n'

  return code

def implInitCode(apis, args):

  code = ''
  for api in apis:
    name = api.name.lower()

    if name == 'gl':

      states = []
      for state in api.states:
        states.append(state.getValue.lower())

      for state in sorted(states):
        code += '  gl_%s(0),\n' % (state)

      code += '  gl_max_varying_floats(0),\n'
      code += '  gl_quads_follow_provoking_vertex_convention(GL_FALSE)\n'

  return code

def implGetCode(apis, args):

  code = '''
  gl_max_attrib_stack_depth = 0;
  gl_max_client_attrib_stack_depth = 0;
  gl_max_combined_texture_image_units = 0;
  gl_max_debug_message_length = 1024;
  gl_max_draw_buffers = 0;
  gl_max_texture_coords = 0;
  gl_max_texture_units = 0;
  gl_max_vertex_attrib_bindings = 0;
  gl_max_vertex_attribs = 0;
  gl_max_viewports = 0;
  gl_max_varying_floats = 0;

  // Looking at the various specs and RegalEmu.h I came up with this table:
  //
  //                                        GL       Core  ES1  ES2  ES3  Regal
  // GL_MAX_ATTRIB_STACK_DEPTH              16        rem  n/a  n/a  n/a    16
  // GL_MAX_CLIENT_ATTRIB_STACK_DEPTH       16        rem  n/a  n/a  n/a    16
  // GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS    96        96    -    8   32     96
  // GL_MAX_DRAW_BUFFERS                     8         8    -    -    4      8
  // GL_MAX_TEXTURE_COORDS                   8        rem   -    -    -     16
  // GL_MAX_TEXTURE_UNITS                    2        rem   +    -    -      4
  // GL_MAX_VARYING_VECTORS                 15        15    -    8   15      -
  // GL_MAX_VARYING_FLOATS                  32 (2.0)  dep   -    -    -      -
  // GL_MAX_VERTEX_ATTRIBS                  16        16    -    8   16     16
  // GL_MAX_VERTEX_ATTRIB_BINDINGS          16        16    -    -    -     16
  // GL_MAX_VIEWPORTS                       16        16    -    -    -     16

  if (compat)
  {
    context.dispatcher.driver.glGetIntegerv( GL_MAX_ATTRIB_STACK_DEPTH, reinterpret_cast<GLint *>(&gl_max_attrib_stack_depth));
    context.dispatcher.driver.glGetIntegerv( GL_MAX_CLIENT_ATTRIB_STACK_DEPTH, reinterpret_cast<GLint *>(&gl_max_client_attrib_stack_depth));
  }

  if (!es1)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS, reinterpret_cast<GLint *>(&gl_max_combined_texture_image_units));

  if (core || compat)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_DRAW_BUFFERS, reinterpret_cast<GLint *>(&gl_max_draw_buffers));

  if (compat)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_TEXTURE_COORDS, reinterpret_cast<GLint *>(&gl_max_texture_coords));

  if (es1 || compat)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_TEXTURE_UNITS, reinterpret_cast<GLint *>(&gl_max_texture_units));

  if (es2 || core)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_VARYING_VECTORS, reinterpret_cast<GLint *>(&gl_max_varying_floats));
  else if (compat)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_VARYING_FLOATS, reinterpret_cast<GLint *>(&gl_max_varying_floats));

  if (es1)
    gl_max_vertex_attribs = 8;  //<> one of these things is not like the other...
  else
    context.dispatcher.driver.glGetIntegerv( GL_MAX_VERTEX_ATTRIBS, reinterpret_cast<GLint *>(&gl_max_vertex_attribs));

  if ((core || compat) && (gl_version_4_3 || gl_arb_vertex_attrib_binding))
    context.dispatcher.driver.glGetIntegerv( GL_MAX_VERTEX_ATTRIB_BINDINGS, reinterpret_cast<GLint *>(&gl_max_vertex_attrib_bindings));

  if ((core || compat) && (gl_version_4_1 || gl_arb_viewport_array))
    context.dispatcher.driver.glGetIntegerv( GL_MAX_VIEWPORTS, reinterpret_cast<GLint *>(&gl_max_viewports));

  if (gl_arb_debug_output)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_DEBUG_MESSAGE_LENGTH_ARB, reinterpret_cast<GLint *>(&gl_max_debug_message_length));
  else if (gl_khr_debug)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_DEBUG_MESSAGE_LENGTH, reinterpret_cast<GLint *>(&gl_max_debug_message_length));
  else if (gl_amd_debug_output)
    context.dispatcher.driver.glGetIntegerv( GL_MAX_DEBUG_MESSAGE_LENGTH_AMD, reinterpret_cast<GLint *>(&gl_max_debug_message_length));

  if ((compat) && (gl_version_3_2 || gl_arb_provoking_vertex || gl_ext_provoking_vertex))
    context.dispatcher.driver.glGetBooleanv( GL_QUADS_FOLLOW_PROVOKING_VERTEX_CONVENTION, &gl_quads_follow_provoking_vertex_convention);
'''
  return code

def originalImplGetCode(apis, args):

  code = ''
  for api in apis:
    name = api.name.lower()

    if name == 'gl':

      states = []
      for state in api.states:
        states.append(state.getValue)

      code += '  if (es1)\n'
      code += '  {\n'

      for state in sorted(states):
        code += '    gl_%s = 0;\n' % state.lower()

      code += '\n'
      code += '    gl_max_vertex_attribs = 8;\n'
      code += '  }\n'
      code += '  else\n'
      code += '  {\n'


      for state in sorted(states):
        if state not in [ 'MAX_VERTEX_ATTRIB_BINDINGS', 'MAX_VIEWPORTS' ]:
          code += '    context.dispatcher.driver.glGetIntegerv( GL_%s, reinterpret_cast<GLint *>(&gl_%s));\n' % (state, state.lower())

      code += '''
    if (gl_version_4_3 || gl_arb_vertex_attrib_binding)
      context.dispatcher.driver.glGetIntegerv( GL_MAX_VERTEX_ATTRIB_BINDINGS, reinterpret_cast<GLint *>(&gl_max_vertex_attrib_bindings));
    else
      gl_max_vertex_attrib_bindings = 0;
    if (gl_version_4_1 || gl_arb_viewport_array)
      context.dispatcher.driver.glGetIntegerv( GL_MAX_VIEWPORTS, reinterpret_cast<GLint *>(&gl_max_viewports));
    else
      gl_max_viewports = 0;
'''

      code += '    context.dispatcher.driver.glGetIntegerv( es2 ? GL_MAX_VARYING_VECTORS : GL_MAX_VARYING_FLOATS, reinterpret_cast<GLint *>(&gl_max_varying_floats));\n'
      code += '  }\n'
      code += '\n'

      code += '\n'

  return code

def extensionStringCode(apis, args):

  code = ''

  for api in apis:
    name = api.name.lower()
    if name in cond:
      code += '#if %s\n'%cond[name]
    for c in sorted(api.categories):
      code += '  %s = stringSetFind(e,"%s");\n' % (c.lower(),c)
    if name in cond:
      code += '#endif\n'
    code += '\n'

  return code

def getExtensionCode(apis, args):

  code = ''
  code += 'bool\n'
  code += 'ContextInfo::getExtension(const char *ext) const\n'
  code += '{\n'
  code += '  Internal("ContextInfo::getExtension ",boost::print::quote(ext,\'"\'));\n'
  code += '\n'

  for api in apis:

    name = api.name.lower()
    if name in cond:
      code += '#if %s\n'%cond[name]
    for c in sorted(api.categories):
      code += '  if (!strcmp(ext,"%s")) return %s;\n' % (c,c.lower())
    if name in cond:
      code += '#endif\n'
    code += '\n'

  code += 'return false;\n'
  code += '}\n\n'

  return code

def generateContextInfoHeader(apis, args):

    substitute = {}
    substitute['LICENSE']         = args.license
    substitute['AUTOGENERATED']   = args.generated
    substitute['COPYRIGHT']       = args.copyright
    substitute['HEADER_NAME']     = "REGAL_CONTEXT_INFO"
    substitute['VERSION_DECLARE'] = versionDeclareCode(apis,args)
    substitute['IMPL_DECLARE']    = implDeclareCode(apis,args)
    outputCode( '%s/RegalContextInfo.h' % args.srcdir, contextInfoHeaderTemplate.substitute(substitute))

def generateContextInfoSource(apis, args):

    substitute = {}
    substitute['LICENSE']        = args.license
    substitute['AUTOGENERATED']  = args.generated
    substitute['COPYRIGHT']      = args.copyright
    substitute['VERSION_INIT']   = versionInitCode(apis,args)
    substitute['VERSION_DETECT'] = versionDetectCode(apis,args)
    substitute['EXT_INIT']       = extensionStringCode(apis,args)
    substitute['EXT_CODE']       = getExtensionCode(apis,args)
    substitute['IMPL_INIT']      = implInitCode(apis,args)
    substitute['IMPL_GET']       = implGetCode(apis,args)
    outputCode( '%s/RegalContextInfo.cpp' % args.srcdir, contextInfoSourceTemplate.substitute(substitute))
