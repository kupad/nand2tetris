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

(LOOP)

//@ncolor <- 0
(WHITE)
@0
D=A
@ncolor
M=D

//read in keyboard:
//If it's anything but zero, the next color is black
(READ)
@KBD
D=M
@RESETIFCHANGE
D;JEQ

//@ncolor <- -1
//Note: we know ncolor is 0 right now. so we can just decr
(BLACK)
@ncolor
M=M-1

//reset @screenptr if color != ncolor 
//if: color+ncolor+1==0, then we changed
(RESETIFCHANGE)
@color
D=M
@ncolor
D=D+M
D=D+1
@SETCOLOR
D;JNE
@SCREEN
D=A
@screenptr
M=D

//@color <- @ncolor
(SETCOLOR)
@ncolor
D=M
@color
M=D

// [@screenptr] <- @color
@color
D=M
@screenptr
A=M
M=D

//@screenptr <- @screenptr +1
@screenptr
M=M+1

@LOOP
0;JMP

