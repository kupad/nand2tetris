// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Fill.asm

// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen,
// i.e. writes "black" in every pixel;
// the screen should remain fully black as long as the key is pressed. 
// When no key is pressed, the program clears the screen, i.e. writes
// "white" in every pixel;
// the screen should remain fully clear as long as no key is pressed.

(MAINLOOP)

//set @color to white.
//@color <- 0 
@0
D=A
@color
M=D

//read in keyboard:
//If it's anything but zero, the @color will be set to black.
@KBD
D=M
@DRAW
D;JEQ

//set @color to black.
//NOTE: we know color is 0 right now. so we can just decr @color
//@color <- @color - 1
@color
M=M-1

(DRAW)
//@screenptr <- @SCREEN
@SCREEN
D=A
@screenptr
M=D

//NOTE: @SREEN's last pixel is at 24575
//while @screenptr < 24576, fill screen with @color
(DRAWLOOP)
@24576
D=A
@screenptr
D=D-M
@ENDDRAW
D;JLE

    //set the address @screenptr is pointing at to @color
    // [@screenptr] <- @color
    @color
    D=M
    @screenptr
    A=M
    M=D

    //@screenptr <- @screenptr + 1
    @screenptr
    M=M+1

    @DRAWLOOP
    0;JMP

(ENDDRAW)

//go back to the main loop
@MAINLOOP
0;JMP

