import std.stdio;
import core.runtime;

static this( ) {
	writefln( "Hello, Module constructor!" );
}

class Foo {
	static void staticbar( ) {
		writefln( "Hello, Static!" );
	}
	
	void methodbar( ) {
		writefln( "Hello, Method!" );
	}
}

extern (C) void c_bar( ) {
	writefln( "Hello, extern C!" );
}