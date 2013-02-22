module dtypes.loader;

import core.runtime;

extern (C) void _d_runtime_initialize( ) {
	Runtime.initialize( );
}

extern (C) void _d_runtime_terminate( ) {
	Runtime.terminate( );
}
