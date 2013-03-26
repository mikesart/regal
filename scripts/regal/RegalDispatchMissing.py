#!/usr/bin/python -B

from string import Template, upper, replace

from ApiUtil import outputCode
from ApiUtil import typeIsVoid

from ApiCodeGen import *

from RegalDispatchLog import apiDispatchFuncInitCode
from RegalDispatchEmu import dispatchSourceTemplate
from RegalContextInfo import cond

##############################################################################################

# CodeGen for missing dispatch functions

def apiMissingFuncDefineCode(apis, args):

  code = ''
  categoryPrev = None

  for api in apis:

    code += '\n'
    if api.name in cond:
      code += '#if %s\n' % cond[api.name]

    for function in api.functions:

      if not function.needsContext:
        continue

      if getattr(function,'regalOnly',False)==True:
        continue

      name   = function.name
      params = paramsDefaultCode(function.parameters, True)
      callParams = paramsNameCode(function.parameters)
      rType  = typeCode(function.ret.type)
      category  = getattr(function, 'category', None)
      version   = getattr(function, 'version', None)

      if category:
        category = category.replace('_DEPRECATED', '')
      elif version:
        category = version.replace('.', '_')
        category = 'GL_VERSION_' + category

      # Close prev category block.
      if categoryPrev and not (category == categoryPrev):
        code += '\n'

      # Begin new category block.
      if category and not (category == categoryPrev):
        code += '// %s\n\n' % category

      categoryPrev = category

      code += 'static %sREGAL_CALL %s%s(%s) \n{\n' % (rType, 'missing_', name, params)
      for param in function.parameters:
        code += '  UNUSED_PARAMETER(%s);\n' % param.name
      code += '  Warning( "%s not available." );\n' % name
      if not typeIsVoid(rType):
        if rType[-1] != '*':
          code += '  return (%s)0;\n' % ( rType )
        else:
          code += '  return NULL;\n'
      code += '}\n\n'

    if api.name in cond:
      code += '#endif // %s\n' % cond[api.name]
    code += '\n'

  return code

def generateMissingSource(apis, args):

  # Output

  substitute = {}

  substitute['LICENSE']         = args.license
  substitute['AUTOGENERATED']   = args.generated
  substitute['COPYRIGHT']       = args.copyright
  substitute['DISPATCH_NAME'] = 'Missing'
  substitute['LOCAL_INCLUDE'] = ''
  substitute['LOCAL_CODE']    = ''
  substitute['API_DISPATCH_FUNC_DEFINE'] = apiMissingFuncDefineCode( apis, args )
  substitute['API_DISPATCH_FUNC_INIT']   = apiDispatchFuncInitCode( apis, args, 'missing' )
  substitute['IFDEF'] = ''
  substitute['ENDIF'] = ''

  outputCode( '%s/RegalDispatchMissing.cpp' % args.srcdir, dispatchSourceTemplate.substitute(substitute))

