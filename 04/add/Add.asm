// Adds R0 and R1 and stores the result in R2.

//D <- R1
@R0
D=M

//D <- D(R1) + R2
@R1
D=D+M

//R2 <- D
@R2
M=D

(END)
@END
0;JMP
