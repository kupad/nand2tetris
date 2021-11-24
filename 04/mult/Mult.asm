// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Mult.asm

// Multiplies R0 and R1 and stores the result in R2.
// (R0, R1, R2 refer to RAM[0], RAM[1], and RAM[2], respectively.)
//
// This program only needs to handle arguments that satisfy
// R0 >= 0, R1 >= 0, and R0*R1 < 32768.

//Plan: add R0 to itself R1 times, using D as an accumulator
//Note: This program modifies the value of R2, leaving it as zero at the end
//R2 <- 0
//While R1 > 0:
//  R2 <- R2 + R0
//  R1 <- R1 - 1

//R2 <- 0
@0
D=A
@R2
M=D

(LOOP)

//exit LOOP if R1 is 0
@R1
D=M
@END
D;JEQ

//R2 <- R2+R0
@R0
D=M
@R2
M=D+M

//R1 <- R1-1
@R1
M=M-1

//GOTO LOOP
@LOOP
0;JMP

(END)
@END
0;JMP

