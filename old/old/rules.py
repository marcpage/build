
# only run to export our modules to other preflight, run and postflight scripts
if __mode__ != "__self__" and __phase__ == "__preflight__":
	pass # export modules here

# only run right before we are going to export ourselves
if __phase__ == "__postflight__" and __mode__ == "__self__":
	import os
	# clean up any python compiled modules before exporting
	os.system("rm -f '%s'/*.pyc"%(os.path.split(__file__)[0]))
