all:
	dmd dtypes-loader.d -ofdtypes-loader -shared
	dmd test.d -oftest -shared