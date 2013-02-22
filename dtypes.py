from ctypes import *

import subprocess
import re, string
import json

def DArray( elementType ):
	class DArray(Structure):
		_fields_ = [
			( 'length', c_size_t ),
			( 'ptr', POINTER(elementType) ),
		]
		
		def __len__( self ):
			return self.length
		
		def __iter__( self ):
			return ( self.ptr[i] for i in range(self.length) ).__iter__( )
	return DArray

class DString(DArray(c_char)):
	def __unicode__( self ):
		return self.ptr[0:len(self)]

class ModuleInfo(Structure):
	_fields_ = [
		( 'name', DString ),
	]

def DDelegate( returnType, *functionArgTypes ):
	functionType = CFUNCTYPE( returnType, c_void_p, *functionArgTypes )
	
	class DDelegate(Structure):
		_fields_ = [
			( 'ptr', c_void_p ),
			( 'funcptr', functionType ),
		]
		
		def __init__( self, func ):
			def delegate( this, *args ):
				return func( *args )
			
			super(DDelegate, self).__init__( 0, functionType(delegate) )
	return DDelegate

ModuleInfoApplyDelegate = DDelegate( c_int, POINTER(ModuleInfo) )

class DContext(object):
	def __init__( self ):
		self.coreLib = cdll.LoadLibrary( 'dtypes-loader.dylib' )
		self.initialiseCoreLibrary( )
		
	def loadLibrary( self, libraryName ):
		lib = cdll.LoadLibrary( libraryName )
		
		for symbol in NameList.listNames( lib, 'thread_entryPoint' ):
			if not symbol.startswith( 'D' ): continue
			s = DMangler.demangleSymbol( symbol )
			
			print json.dumps( s, indent=4 )
		
		return DLibrary( lib )
		
	def initialiseCoreLibrary( self ):
		self.coreLib._d_runtime_initialize( )
		
		getName = self.coreLib.D6object10ModuleInfo4nameMFNaNbNdZAya
		getName.restype = DString
		
		def d( moduleInfo ):
			moduleName = unicode( getName( moduleInfo.contents ) )
			
			if '/' in moduleName:
				return 0
			
			print moduleName
			
			return 0
		
		delegate = ModuleInfoApplyDelegate( d )
		
		self.coreLib.D6object10ModuleInfo7opApplyFMDFKPS6object10ModuleInfoZiZi( delegate )
		
		"""
		ModuleInfoArrType = DArray( ModuleInfo )
		
		moduleInfoList = ModuleInfoArrType.in_dll( self.coreLib, "_moduleinfo_array" )
		
		print moduleInfoList
		print moduleInfoList.length
		print moduleInfoList.ptr
		print len(moduleInfoList)
		for moduleInfo in moduleInfoList:
			print self.coreLib.D6object10ModuleInfo5isNewMFNaNbNdZb( pointer(moduleInfo) )
			#print moduleInfo.name
		"""
	
	def __getattr__( self, moduleName ):
		return DModule( self, moduleName )

class DLibrary(object):
	def __init__( self, lib ):
		self.cdll = lib

class DMangler(object):
	@classmethod
	def mangleSeparatedString( cls, parts ):
		out = ['D']
		for p in parts:
			out.append( str(len(p)) )
			out.append( p )
		
		return ''.join( out )
	
	@classmethod
	def mangleFunction( cls, methodParts, requiresThis=False ):
		methodMangled = cls.mangleSeparatedString( methodParts )
		
		funcMangleParts = [methodMangled]
		
		if requiresThis:
			funcMangleParts.append( 'M' )
		
		# calling convention: D -> "F"
		funcMangleParts.append( 'F' )
		
		return ''.join( funcMangleParts )
	
	@classmethod
	def demangleQualifiedName( cls, mangled ):
		rest = mangled
		
		names = []
		
		while len(rest) > 0 and rest[0] in string.digits:
			match = re.match( '^(\d*)(.*)', rest )
			
			size = int( match.group(1) )
			rest = match.group(2)
			
			name = rest[:size]
			rest = rest[size:]
			
			if len(rest) > 0 and rest[0] not in string.digits:
				name = {
					'name': name,
				}
				typeData, rest = cls.demangleType( rest )
				name.update( typeData )
			
			names.append( name )
		
		return names, rest
	
	@classmethod
	def demangleSymbol( cls, mangled ):
		if not mangled.startswith( 'D' ):
			return None
		
		rest = mangled[1:]
		
		names, rest = cls.demangleQualifiedName( rest )
		
		last = None
		if isinstance(names[-1], dict):
			last = names[-1]
			names = names[:-1] + [names[-1]['name']]
		
		data = {}
		
		if last is not None:
			data.update( last )
		
		data.update( {
				'mangled': mangled,
				'name': tuple(names),
		} )
		
		return data
	
	@classmethod
	def demangleType( cls, mangled ):
		if mangled == 'Z':
			return {}, ''
		
		rest = mangled
		
		dtype = {
		
		}
		
		if rest.startswith( 'M' ):
			dtype['scope'] = True
			rest = rest[1:]
		
		for code, callingConvention in { 'F': 'D', 'U': 'C', 'W': 'Windows', 'V': 'Pascal', 'R': 'C++' }.iteritems():
			if rest.startswith( code ):
				rest = rest[1:]
				dtype['function'] = True
				dtype['callingConvention'] = callingConvention
				
				dtype['functionAttributes'] = {}
				for attr, functionAttribute in { 'Na': 'pure', 'Nb': 'nothrow', 'Nc': 'ref', 'Nd': 'property', 'Ne': 'trusted', 'Nf': 'safe' }.iteritems( ):
					if rest.startswith( attr ):
						rest = rest[len(attr):]
						dtype['functionAttributes'][functionAttribute] = True
				
				dtype['arguments'] = []
				while len(rest) > 0 and rest[0] not in ['X','Y','Z']:
					arg, nrest = cls.demangleType( rest )
					assert nrest != rest, nrest
					rest = nrest
					dtype['arguments'].append( arg )
				
				if len(rest) > 0:
					dtype['variadicStyle'] = rest[0]
					rest = rest[1:]
					
					dtype['returnType'], rest = cls.demangleType( rest )
				
				return dtype, rest
		
		if rest.startswith( 'D' ):
			# delegate
			delegateType, rest = cls.demangleType( rest[1:] )
			
			return {
				'delegate': delegateType,
			}, rest
		
		direction = {
			'J': 'out',
			'K': 'ref',
			'L': 'lazy',
		}
		
		for sig, dirname in direction.iteritems():
			if rest.startswith( sig ):
				data, rest = cls.demangleType( rest[len(sig):] )
				data[dirname] = True
				return data, rest
		
		modifiers = {
			'O': 'shared',
			'x': 'const',
			'y': 'immutable',
			'Ng': 'wild',
			'A': 'array',
		}
		
		for sig, modname in modifiers.iteritems():
			if rest.startswith( sig ):
				data, rest = cls.demangleType( rest[len(sig):] )
				data[modname] = True
				return data, rest
		
		basicTypes = {
			'v': 'void',
			'g': 'byte',
			'h': 'ubyte',
			's': 'short',
			't': 'ushort',
			'i': 'int',
			'k': 'uint',
			'l': 'long',
			'm': 'ulong',
			'f': 'float',
			'd': 'double',
			'e': 'real',
			'o': 'ifloat',
			'p': 'idouble',
			'j': 'ireal',
			'q': 'cfloat',
			'r': 'cdouble',
			'c': 'creal',
			'b': 'bool',
			'a': 'char',
			'u': 'wchar',
			'w': 'dchar',
			'n': 'null',
		}
		
		for sig, typename in basicTypes.iteritems():
			if rest.startswith( sig ):
				return { 'type': typename }, rest[1:]
		
		qualifiedTypes = {
			'I': 'ident',
			'C': 'class',
			'S': 'struct',
			'E': 'enum',
			'T': 'typedef',
		}
		
		for sig, qualifiedType in qualifiedTypes.iteritems():
			if rest.startswith( sig ):
				rest = rest[1:]
				names, rest = cls.demangleQualifiedName( rest )
				data = {
					'type': (qualifiedType, names),
				}
				return data, rest
		
		if rest.startswith( 'G' ):
			# static array
			match = re.match( '^G(\d*)(.*)', rest )
			
			size = int( match.group(1) )
			rest = match.group(2)
			
			data, rest = cls.demangleType( rest[len(sig):] )
			
			return {
				'array': data,
				'size': size,
			}, rest
		
		if rest.startswith( 'H' ):
			# assoc array
			rest = rest[1:]
			keyType, rest = cls.demangleType( rest )
			valueType, rest = cls.demangleType( rest )

			return {
				'associativeArray': {
					'key': keyType,
					'value': valueType,
				},
			}, rest
		
		if rest.startswith( 'P' ):
			# pointer
			rest = rest[1:]
			derefType, rest = cls.demangleType( rest )

			return {
				'pointer': derefType
			}, rest
		
		return dtype, rest

class DMethod(object):
	def __init__( self, context, thisPtr, methodName ):
		self.context = context
		self.thisPtr = thisPtr
		self.methodName = methodName
	
	def __repr__( self ):
		return '<DMethod %s>' % self.methodName
	
	def __call__( self ):
		print 'D6object10ModuleInfo4nameMFNaNbNdZAya'
		print DMangler.mangleFunction( self.methodName.split( '.' ), requiresThis=True )

class DStruct(object):
	def __init__( self, context, structName, structPtr ):
		self.context = context
		self.structName = structName
		self.structPtr = structPtr
	
	def __getattr__( self, methodName ):
		methodPath = self.structName + '.' + methodName
		return DMethod( self.context, self.structPtr, methodPath )

class DModule(object):
	def __init__( self, context, moduleName ):
		self.context = context
		self.moduleName = moduleName
	
	def __getattr__( self, subModuleName ):
		return DModule( self.context, self.moduleName + '.' + subModuleName )
	
	def __repr__( self ):
		return '<DModule %s>' % self.moduleName
	
	@property
	def _moduleInfoName( self ):
		return DMangler.mangleSeparatedString( self.moduleName.split( '.' ) + ['__ModuleInfo'] ) + 'Z'
	
	@property
	def _moduleInfo( self ):
		try:
			return DStruct( self, 'object.ModuleInfo', ModuleInfo.in_dll( self.context.coreLib, self._moduleInfoName ) )
		except ValueError:
			return None
	
	def isReal( self ):
		return ( self._moduleInfo is not None )

class DL_info(Structure):
	_fields_ = [
		('dli_fname', c_char_p),
		('dli_fbase', c_void_p),
		('dli_sname', c_char_p),
		('dli_saddr', c_void_p),
	]

class NameList(object):
	@classmethod
	def listNames( cls, ctypes_library, any_function_name ):
		"""Given a ctypes library pointer and the name of any single function
		that is exported in that library, returns a list of all functions
		exported in the library.
		
		Uses the command line 'nm' utility.
		"""
		
		info = DL_info( )
		print CDLL( 'libc.dylib' ).dladdr( getattr(ctypes_library, any_function_name), byref(info) )
		
		for symbol in subprocess.check_output( ["nm", "-U", info.dli_fname] ).split('\n'):
			try:
				(sym_address, sym_type, sym_name) = symbol.split( ' ' )
			except ValueError:
				continue

			if not sym_name.startswith( '_' ):
				continue
			
			yield sym_name[1:]

if __name__ == '__main__':
	dlang = DContext( )
	dlang.loadLibrary( 'test.dylib' )
	
	#print dlang.rt
	#print dlang.rt.minfo
	
	#print dlang.rt.minfo._moduleInfo.name
	#print dlang.rt.minfo._moduleInfo.name( )
	
	#lib = dlang.loadLibrary( 'test.dylib' )