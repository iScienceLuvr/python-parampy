import types,inspect
from definitions import SIDispenser
from quantities import Quantity,SIQuantity
from units import Units
import numpy as np
import sympy
import physical_constants
from text import colour_text
import re

class Parameters(object):
	"""
	Parameters(dispenser=None,default_scaled=True,constants=False)
	
	An object to manage the generation of scaled parameters; as well as 
	handle the dependence of parameters upon one another.
	
	Parameters
	----------
	dispenser : Should provide None or a custom unit dispenser. If None is 
		provided, Parameters will instantiate an SIDispenser; which hosts
		the standard units relative to an SI basis.
	default_scaled : Whether the created Parameter object should by default
		return scaled (unitless) parameters.
	constants : Whether Parameters should import the physical constants when
		unit dispenser is subclass of SIDispenser.
	
	Examples
	--------
	
	Initialising a parameters object with the default settings
	>>> p = Parameters()
	
	## Parameter Extraction
		
		To retrieve a parameter 'x' from a Parameters instance, you use:
		>>> p('x')
		If default_scaled = True, then this will yield a scaled float. Otherwise
		this will return a Quantity object, which keeps track of units. 
		To invert this, simply prepend a '_' to the parameter name.
		>>> p('_x')
		
		Provided that the parameter name does not clash with any methods
		of the Parameters object, you can use a shorthand for this:
		>>> p.x
		>>> p._x
		
		You can also temporarily override parameters while retrieving them,
		which is useful especially for functions of parameters. For example,
		if we want to extract 'y' when 'x'=2, without permanently changing
		the value of 'x', we could use:
		>>> p('y',x=2)
	
	## Parameter Setting
	
		Set a parameter value 'x' to 1 ms.
		>>> p(x=(1,'ms'))
		Parameter names must start with a letter or underscore; and may contain
		any number of letters, numbers, and underscores.
		
		When a unit is not specified, the parameter is assumed to be a
		scaled version of the parameter. If the unit has never been set, 
		then a 'constant' unit is assumed; otherwise the older unit is used.
		>>> p(x=1)
		
		You can specify the units of a parameter, without specifying its
		value:
		>>> p & {'x':'ms'}
		Note that if you do this when the parameter has already been set 
		that the parameter will have its units changed, but its value
		will remain unchanged. Use this carefully.
		
		Set a parameter 'y' that depends on the current scaled value of 
		'x' (if default_scale = True)
		>>> p(y=lambda x: x**2)
		OR
		>>> p(y= <function with argument 'x'>)	
		
		If one wanted to use the united Quantity instead, they would use:
		>>> p(y=lambda _x: _x**2)
		Which would keep track of the units.
		
		We can set 'y' to have units of 'ms^2', even when using the scaled values.
		>>> p & {'y':'ms^2'}
		
		One can also set a parameter to *always* depend on another parameter.
		>>> p << {'y':lambda x: x**2}
		Now, whenever x is changed, y will change also.
		
		If you want 'x' to change with 'y', then you simply set 'y' as 
		an invertable function of 'x'. If the argument 'y' is specified, 
		the function should return the value of 'x'. e.g.
		>>> p << { 'y': lambda x,y=None: x**2 if y is None else math.sqrt(y) }
		
		Such relationships can be chained. For instance, we could set an invertible 
		function for 'z' as a function of 'x' and 'y'. Note that when an invertible
		function is inverted, it should return a tuple of variables in the
		same order as the function declaration.
		>>> p << { 'z': lambda x,y,z=None: x**2+y if z is None else (1,2) }
		
		We can then update z in the normal way:
		>>> p(z=1)
		This results in Parameters trying to resolve y=2 => x= sqrt(2) and 
		x=1. This will return a ValueError with a description of the problem.
		However, this allows one to have an intricate variable structure.
		
		To force parameters to be overridden, whether or not the parameter is
		a function, use the left shift operator:
		>>> p << {'z': (1,'ms')}
	
	## Removing Parameters
		
		To remove a parameter, simply use the subtraction operator:
		>>> p - 'x'
	
	## Parameter Units and Scaling
		
		You can add your own custom units by adding them directly to the
		unit dispenser used to set up the Parameters instance; or by 
		adding them to the parameters object like:
		>>> p + {'names':'testunit','abbr':'TU','rel':1e7,'length':1,'mass':1,'prefixable':False}
		For a description of what the various keys mean, see the documentation
		for Unit.
		
		It is sometimes useful to have a scaled representation of the 
		parameters that is different from the standard SI values. You can set
		a new basis unit for any dimension: i.e.  For the below, all scaled 'length'
		parameters will be scaled by 0.5 compared to the former basis of (1,'m').
		>>> p * {'length':(2,'m')}
		
		You can also change the scaling for particular combinations of dimensions
		on top of the basis scalings. The below will cause all "acceleration" 
		parameters to be multiplied by 2.5 in their scaled forms.
		>>> p * ({'length':1,'time':-2},2.5)
	
	## Unit Conversion
		
		It is useful to have a mechanism that scales all physical units
		in the same way as your parameters. Parameters instances allow 
		you to convert physical units to and from the internal representation
		used by the Parameters object.
		
		For example:
		>>> p.convert( 1.0 , input='ms')
		converts 1 ms to the internal scaled representation of that parameter.
		Whereas:
		>>> p.convert( 1.0 , output='ms')
		converts a scaled parameter with dimension of 'time' to a Quantity
		with units of 'ms'.
	
	## Physical Constants
		
		To make life easier, Parameters instances also broadcasts the physical
		constants defined in "physical_constants.py" when using an SIDispenser
		if constants is set to 'True'. These constants function just as 
		any other parameter, and can be overriden. For example:
		>>> p.hbar
	
	## Loading and Saving
		
		To load a parameter set into a Parameters instance, use the classmethod:
		>>> p = Parameters.load( "filename.py" )
		To see the format of a parameters instance, or to save your existing parameters,
		use:
		>>> p >> "filename.py"
	
	"""
	# Parameters are retrieved as:
	# pams.<var> returns stored value or function
	# pams.<var>(<pams>)
	
	def __init__(self,dispenser=None,default_scaled=True,constants=False):
		self.__parameters_spec = {}
		self.__parameters = {}
		self.__scalings = {}
		self.__unit_scalings = []
		self.__units = dispenser if dispenser is not None else SIDispenser()
		self.__units_custom = []
		self.__default_scaled = default_scaled
		
		self.__scaling_cache = {}
		
		if constants and isinstance(self.__units,SIDispenser):
			self(**physical_constants.constants)
	
	############## PARAMETER OBJECT CONFIGURATION ##############################
	def __add__(self,other):
		self.__unit_add(**other)
		return self
		
	def __unit_add(self,**options):
		'''
		This adds a unit to a custom UnitDispenser. See UnitDispenser.add for more info.
		'''
		self.__units.add(**options)
		self.__units_custom.append(options)
	
	def __mul__(self,other):
		self.__scaling_set(other)
		return self
		
	def __scaling_set(self,kwargs):
		self.__scaling_cache = {}
		
		# If kwargs is dict, then add a new dimension scaling
		if isinstance(kwargs,dict):
			for arg in kwargs:
				if arg in self.__units.dimensions:
					scale = self.__get_quantity(kwargs[arg],param=arg)
					if scale.units.dimensions == {arg:1}:
						self.__scalings[arg] = scale
					else:
						print "Warning: Dimension of scaling is wrong for %s" % arg
				else:
					print "Error: Invalid scaling dimension."
		
		# Otherwise, add a new unit scaling
		elif isinstance(kwargs,(list,tuple)) and len(kwargs)==2:
			self.__unit_scalings.append(kwargs)
		
		else:
			raise ValueError, "Cannot set scaling with %s" % kwargs
	
	def __get_unit(self,unit):
		
		if isinstance(unit,str):
			return self.__units.get(unit)
		
		elif isinstance(unit,Units):
			return unit
		
		raise ValueError, "No coercion for %s to WorkingUnit." % unit
			
	############# PARAMETER RETRIEVAL ##########################################
	
	def __get(self,*args,**kwargs):
		'''
		Retrieve the parameters specified in args, with temporary values overriding
		defaults as in kwargs. Parameters are returned as Quantity's.
		'''
		
		self.__process_override(kwargs)
		
		return self.__get_params(*args,**kwargs)
	
	def __get_params(self,*args,**kwargs):
		
		if len(args) == 1:
			return self.__get_param(args[0],**kwargs)
		
		rv = {}
		for arg in args:
			rv[self.__get_pam_name(arg)] = self.__get_param(arg,**kwargs)
		
		return rv
		
	
	def __get_param(self,arg,**kwargs):
		'''
		Returns the value of a param `arg` with its dependent variables overriden
		as in `kwargs`.
		'''
		
		# If the parameter is actually a function
		if not isinstance(arg,str) or (self.__get_pam_name(arg) not in kwargs and self.__get_pam_name(arg) not in self.__parameters):
			return self.__eval(arg,**kwargs)
			
		else:
			scaled = self.__default_scaled
			if arg[:1] == "_": #.startswith("_"):
				arg = arg[1:]
				scaled=not scaled
			
			# If the parameter is temporarily overridden, return the override value
			if arg in kwargs:
				return self.__get_quantity(kwargs[arg],param=arg,scaled=scaled)
		
			# If the parameter is a function, evaluate it with local parameter values (except where overridden in kwargs)
			elif isinstance(self.__parameters[arg],types.FunctionType):
				return self.__get_quantity(self.__eval_function(arg,**kwargs)[arg],param=arg,scaled=scaled)
		
			# Otherwise, return the value currently stored in the parameters
			else:
				return self.__get_quantity(self.__parameters[arg],param=arg,scaled=scaled)
	
	def __get_pam_name(self,param):
		if isinstance(param,str):
			if param[:1] == "_":
				return param[1:]
			return param
			#return param if not param.startswith('_') else param[1:]
		return param
	
	def __process_override(self,kwargs,restrict=None):
		'''
		Process kwargs and make sure that if one of the provided overrides 
		corresponds to an invertable function, that the affected variables are also included
		as overrides also. An warning is thrown if these variables are specified also.
		'''
		
		if restrict is None:
			restrict = kwargs.keys()
		
		if len(restrict) == 0:
			return
		
		# Check to see whether override arguments are functions; and if so
		# first evaluate them.
		for pam,val in list(kwargs.items()):
			if pam in restrict:
				if isinstance(val,str):
					val = self.__get_function(val)
				if isinstance(val,types.FunctionType):
					new = kwargs.copy()
					del new[pam]
					kwargs[pam] = self.__get_param(val,**new)
		
		# Now, ratify these changes through the parameter sets to ensure
		# that the effects of these overrides is properly implemented
		new = {}
		for pam,val in kwargs.items():
			if pam in restrict:
				if isinstance(self.__parameters.get(pam),types.FunctionType):
					vals = self.__eval_function(pam,**kwargs)
					for key in vals:
						if key in kwargs and vals[key] != kwargs[key] or key in new and vals[key] != new[key]:
							raise ValueError, "Warning: parameter %s overspecified, with contradictory values." % key
					new.update(vals)
		
		kwargs.update(new)
		self.__process_override(kwargs,restrict=new.keys())
	
	def __eval_function(self,param,**kwargs):
		'''
		Returns a dictionary of parameter values. If the param variable itself is provided,
		then the function has its inverse operator evaluated. Functions must be of the form:
		def f(<pam>,<pam>,<param>=None)
		If <pam> is prefixed with a "_", then the scaled version of the parameter is sent through
		instead of the Quantity version.
		'''
		
		f = self.__parameters.get(param)
		
		# Check if we are allowed to continue
		if param in kwargs and param not in inspect.getargspec(f)[0] and "_"+param not in inspect.getargspec(f)[0]:
			raise ValueError, "Configuration requiring the inverting of a non-invertable map for %s."%param
		
		arguments = []
		for arg in inspect.getargspec(f)[0]:
			
			if arg == param and arg not in kwargs:
				continue
			
			arguments.append(self.__get_param(arg,**kwargs))
		
		r = f(*arguments)
		if not isinstance(r,(tuple,list)):
			r = [r]
		
		# If we are not performing the inverse operation
		if param not in kwargs:
			return {param: self.__get_quantity(r[0],param=param)}
		
		# Deal with the inverse operation case
		inverse = {}
		
		for i,arg in enumerate(inspect.getargspec(f)[0]):
			if arg[:1] == '_': #.startswith('_'):
				pam = arg[1:]
			else:
				pam = arg
			
			if pam != param:
				inverse[arg] = self.__get_quantity(r[i],param=pam)
		
		return inverse
	
	def __get_quantity(self, value, param=None, unit=None, scaled=False):
		'''
		Return a Quantity or scaled float associated with the value provided
		and the dimensions of param.
		'''
		
		q = None
		
		# If tuple of (value,unit) is presented
		if isinstance(value,(tuple,list)):
			if len(value) != 2:
				raise ValueError
			else:
				q = Quantity(*value,dispenser=self.__units)
		
		elif isinstance(value, Quantity):
			q = value
		
		elif isinstance(value,types.FunctionType):
			q = value
		
		else:
			if unit is None and param is None:
				unit = self.__get_unit('')
			elif unit is not None:
				unit = self.__get_unit(unit)
			else:
				unit = self.__get_unit(''  if self.__parameters_spec.get(param) is None else self.__parameters_spec.get(param) )
			q = Quantity(value*self.__unit_scaling(unit), unit,dispenser=self.__units)
		
		if not scaled:
			return q
		
		return q.value/self.__unit_scaling(q.units)

	
	def __eval(self,arg,**kwargs):
		if isinstance(arg,types.FunctionType):
			params = self.__get_params(*inspect.getargspec(arg)[0],**kwargs)
			if not isinstance(params,dict):
				params = {self.__get_pam_name(inspect.getargspec(arg)[0][0]): params}
			return arg(* (val for val in map(lambda x: params[self.__get_pam_name(x)],inspect.getargspec(arg)[0]) ) )
		elif isinstance(arg,str) or arg.__class__.__module__.startswith('sympy'):
			try:
				if isinstance(arg,str):
					arg = sympy.S(arg)
					fs = list(arg.free_symbols)
					if len(fs) == 1 and str(arg)==str(fs[0]):
						raise ValueError, "There is no parameter, and no interpretation, of '%s' which is recognised by Parameters." % arg
				params = {}
				for sym in arg.free_symbols:
					param = self.__get_param(str(sym),**kwargs)
					if isinstance(param,Quantity):
						raise ValueError, "Symbolic expressions can only be evaluated when using scaled parameters."
					params[str(sym)] = self.__get_param(str(sym),**kwargs)
				return arg.subs(params).evalf()
			except ValueError, e:
				raise e
			except KeyError, e:
				raise e
			except Exception, e:
				raise RuntimeError, "Error evaluating symbolic statement '%s'. Ensure that only scaled parameters are being used. The message was: `%s`." % (arg,e)
		
		raise KeyError, "There is no parameter, and no interpretation, of '%s' which is recognised by Parameters." % arg
	
	################ SET PARAMETERS ############################################
	
	def __is_valid_param(self,param):
		return re.match("^[_A-Za-z][_a-zA-Z0-9]*$",param)
	
	def __check_valid_params(self,params):
		bad = []
		for param in params:
			if not self.__is_valid_param(param):
				bad.append(param)
		if len(bad) > 0:
			raise KeyError, "Attempt to set invalid parameters: %s . Parameters must be valid python identifiers matching ^[_A-Za-z][_a-zA-Z0-9]*$." % ','.join(bad)
	
	def __set(self,**kwargs):
		
		self.__check_valid_params(kwargs)
		
		for param,val in kwargs.items():
			try:
				if isinstance(val,(types.FunctionType,str)):
					self.__parameters[param] = self.__check_function(param,self.__get_function(val))
					self.__spec(**{param:self.__get_unit('')})
				elif isinstance(val,(list,tuple)) and isinstance(val[0],(types.FunctionType,str)):
					self.__parameters[param] = self.__check_function(param,self.__get_function(val[0]))
					self.__spec(**{param:self.__get_unit(val[1])})
				else:
					self.__parameters[param] = self.__get_quantity(val,param=param)
					if isinstance(self.__parameters[param],Quantity):
						self.__spec(**{param:self.__parameters[param].units})
			
			except ValueError, e:
				raise ValueError, "Could not add parameter %s. %s" % (param, e)
	
	def __update(self,**kwargs):
		
		self.__check_valid_params(kwargs)
		
		self.__process_override(kwargs)
		
		for param,value in kwargs.items():
			if param not in self.__parameters or not isinstance(self.__parameters.get(param),types.FunctionType):
				self.__set(**{param:kwargs[param]})
				#print param,kwargs[param]
				#self.__parameters[param] = self.__get_quantity(kwargs[param],param=param)
	
	def __and__(self,other):
		if not isinstance(other,dict):
			raise ValueError, "Cannot set the units for parameters without using a dictionary."
		self.__spec(**other)
	
	def __spec(self, **kwargs):
		''' Set units for parameters. '''
		for arg in kwargs:
			self.__parameters_spec[arg] = self.__get_unit(kwargs[arg])
			if self.__parameters.get(arg) is not None:
				self.__parameters[arg].units = self.__parameters_spec[arg]
	
	def __remove(self,param):
		if param in self.__parameters:
			del self.__parameters[param]
		if param in self.__parameters_spec:
			del self.__parameters_spec[param]
	
	def __sub__(self,other):
		if not isinstance(other,str):
			raise ValueError, "Subtractee must be the name of a variable."
		
		self.__remove(other)
		return self
	
	def __lshift__(self,other):
		
		if not isinstance(other,dict):
			raise ValueError
		
		self.__set(**other)
		return self
	
	def __sympy_to_function(self,expr):
		try:
			expr = sympy.S(expr)
			syms = list(expr.free_symbols)
			f = sympy.utilities.lambdify(syms,expr)

			o = {}
			exec ('def g(%s):\n\treturn f(%s)'%( ','.join(map(str,syms)) , ','.join(map(str,syms)) ) , {'f':f},o)

			return o['g']
		except:
			raise ValueError, 'String is not a valid symbolic expression.'
	
	def __get_function(self,expr):
		if isinstance(expr,types.FunctionType):
			return expr
		return self.__sympy_to_function(expr)
		
	def __check_function(self,param,f,forbidden=None):
		args = inspect.getargspec(f).args
		
		while param in args:
			args.remove(param)
		
		if forbidden is None:
			forbidden = []
		else:
			for arg in forbidden:
				if arg in args:
					raise ValueError, "Adding function would result in recursion with function '%s'" % arg
		forbidden.append(param)
		
		for arg in args:
			if isinstance(self.__parameters.get(arg,None),types.FunctionType):
				self.__check_function(arg,self.__parameters.get(arg),forbidden=forbidden[:])
		
		return f
	
	def __unit_scale(self,unit):
		for scale in self.__unit_scalings:
			if scale[0] == unit.dimensions:
				return scale[1]
		return 1.0
	
	def __basis_scale(self,unit):
		unit = self.__get_unit(unit)
		scaling = Quantity(1,None,dispenser=self.__units)
		
		for dim,power in unit.dimensions.items():
			scaling *= self.__scalings.get(dim,Quantity(1,self.__units.basis()[dim],dispenser=self.__units))**power
		
		return scaling
	
	def __unit_scaling(self,unit):
		'''
		Returns the float that corresponds to the relative scaling of the
		provided unit compared to the intrinsic scaling basis of the parameters.
		
		dimensionless value = quantity / unit_scaling = quantity * unit_scale / basis_scale
		'''
		
		if unit in self.__scaling_cache:
			return self.__scaling_cache[unit]
		
		scale = self.__basis_scale(unit)
		scaling = scale.value*scale.units.scale(unit)/self.__unit_scale(unit)
		
		self.__scaling_cache[unit] = scaling
		return scaling
		
	################ EXPOSE PARAMETERS #########################################
	def __call__(self,*args,**kwargs):
		
		if args:
			return self.__get(*args,**kwargs)
		
		self.__update(**kwargs)
		return self
	
	def __table(self,table):
		
		def text_len(text):
			if '\033[' in text:
				return len(text) - 11
			return len(text)
		
		def column_width(i,text):
			if '\033[' in text:
				return col_width[i] + 11
			return col_width[i]
		
		col_width = [max(text_len(x) for x in col) for col in zip(*table)]
		output = []
		for line in table:
			output.append( "| " + " | ".join("{:^{}}".format(x,column_width(i,x)) for i, x in enumerate(line)) + " |" )
		
		return '\n'.join(output)
	
	def __repr__(self):
		
		if len(self.__parameters) == 0:
			return 'No parameters have been specified.'
		
		parameters = [ [colour_text('Parameter','WHITE',True),colour_text('Value','WHITE',True),colour_text('Scaled','WHITE',True)] ]
		for param in sorted(self.__parameters.keys()):
			
			if self.__default_scaled:
				key_scaled,key = param,'_%s'%param
			else:
				key_scaled,key = '_%s'%param, param
			
			if isinstance(self.__parameters[param],types.FunctionType):
				v = 'Unknown'
				vs = 'Unknown'
				try:
					v = str(self.__get(key))
					vs = str(self.__get(key_scaled))
				except:
					pass
				parameters.append( [ 
					'%s(%s)' % ( param, ','.join(inspect.getargspec(self.__parameters[param])[0] ) ),
					v,
					vs  ] )
				
			else:
				parameters.append( [param, str(self.__get(key)),str(self.__get(key_scaled))] )
		
		for param in sorted(self.__parameters_spec.keys()):
			if param not in self.__parameters:
				parameters.append( [colour_text(param,'CYAN'), colour_text("- %s" % self.__parameters_spec[param],'CYAN'),colour_text("-",'CYAN')] )
		
		return self.__table(parameters)
	
	def __dir__(self):
	    res = dir(type(self)) + list(self.__dict__.keys())
	    res.extend(self.__parameters.keys())
	    return res
	
	def __getattr__(self,name):
		if name[:2] == "__":
			raise AttributeError
		return self.__get(name)
	
	################## CONVERT UTILITY #####################################
	def convert(self, quantity, input=None, output=None):
		if input is None and output is None:
			return quantity
		
		if output is None:
			return quantity / self.__unit_scaling(self.__units.get(input))
		
		if input is None:
			return self.__get_quantity(quantity, unit=output)
			#return quantity * self.__unit_scaling(self.__units.get(output))
		
		#unit_in = self.__units.get(input)
		#unit_out = self.__units.get(output)
		return Quantity(quantity, input, dispenser=self.__units)(output)
		#quantity * unit_in.scale(unit_out)
	
	def optimise(self,param):
		'''
		Optimise the parameter query operator to fast operation times.
		'''
		
		if param is None or isinstance(param,types.FunctionType) or self.__is_valid_param(param):
			return param
		
		elif isinstance(param,str):
			return self.__sympy_to_function(param)
		
		raise ValueError, "No way to optimise parameter expression: %s ." % param
	
	################## LOAD / SAVE PROFILES ################################
	
	@classmethod
	def load(cls, filename, **kwargs):
		import imp
		
		profile = imp.load_source('profile', filename)
		
		p = cls(**kwargs)
		
		p*getattr(profile,"dimension_scalings",{})
		
		for unit_scaling in getattr(profile,"unit_scalings",[]):
			p*unit_scaling
		
		for unit in getattr(profile,"units_custom",[]):
			p+unit
		
		p(**getattr(profile,"parameters",{}))
		
		return p
	
	def __rshift__(self,other):
		
		if not isinstance(other, str):
			raise ValueError, "Must be a filename."
		
		self.__save__(other)
		return self
	
	def __save__(self, filename):
		f = open(filename,'w')
		
		# Export dimension scalings
		f.write( "dimension_scalings = {\n" )
		for dimension,scaling in self.__scalings.items():
			f.write("\t\"%s\": (%s,\"%s\"),\n"%(dimension,scaling.value,scaling.units))
		f.write( "}\n\n" )
		
		# Export unit scalings
		f.write( "unit_scalings = {\n" )
		for scaling in self.__unit_scalings:
			f.write("%s,\n"%unit)
		f.write( "}\n\n" )
		
		# Export custom units
		f.write( "units_custom = {\n" )
		for unit in self.__units_custom:
			f.write("%s,\n"%unit)
		f.write( "}\n\n" )
		
		# Export parameters
		f.write( "parameters = {\n" )
		for pam,value in self.__parameters.items():
			f.write("\t\"%s\": (%s,\"%s\"),\n"%(pam,value.value,value.units))
		f.write( "}\n\n" )
		
		f.close()
