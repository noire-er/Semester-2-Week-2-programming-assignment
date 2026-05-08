//
// Starting code for the portfolio exercise. Some required routines are included in a separate
// file (ending '_extra.h'); this file should not be altered, as it will be replaced with a different
// version for assessment.
//
// Compile as normal, e.g.,
//
// > gcc -o portfolioExercise portfolioExercise.c
//
// and launch with the problem size N and number of threads p as command line arguments, e.g.,
//
// > ./portfolioExercise 12 4
//


//
// Includes.
//
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <pthread.h>

#include "portfolioExercise_extra.h"        // Contains routines not essential to the actual portfolio task submission4

// Need global variables

int N_global;
int nThreads_global;
float **M_global;
float *u_global;
float *v_global;
float *partialDotProducts;

typedef struct {
    int threadID;
} ThreadArgs;

// Thread function implemented here

void *ThreadFunc( void *arg )
{
    ThreadArgs *tArgs = (ThreadArgs*) arg;
    int id = tArgs->threadID;

    int rowsPerThread = N_global / nThreads_global;
    int rowStart = id * rowsPerThread;
    int rowEnd   = rowStart + rowsPerThread;

    // Matrix-vector Multiplication

    for( int row=rowStart; row<rowEnd; row++ )
    {
        v_global[row] = 0.0f;
        for( int col=0; col<N_global; col++ )
            v_global[row] += M_global[row][col] * u_global[col];
    }
 
    // Step 2: Partial dot product of v with itself for this thread's rows.
    float partial = 0.0f;
    for( int i=rowStart; i<rowEnd; i++ )
        partial += v_global[i] * v_global[i];
 
    partialDotProducts[id] = partial;
 
    return NULL;
}

int main( int argc, char **argv )
{
    int N, nThreads;
    if( parseCmdLineArgs(argc,argv,&N,&nThreads)==-1 ) return EXIT_FAILURE;
 
    float **M, *u, *v;
    if( initialiseMatrixAndVector(N,&M,&u,&v)==-1 ) return EXIT_FAILURE;
 
    if( N<=12 ) displayProblem( N, M, u, v );
 
    // Set globals.
    N_global        = N;
    nThreads_global = nThreads;
    M_global        = M;
    u_global        = u;
    v_global        = v;
 
    partialDotProducts = (float*) malloc( nThreads * sizeof(float) );
    if( partialDotProducts == NULL ) { printf("ERROR: malloc failed.\n"); return EXIT_FAILURE; }
 
    struct timespec startTime, endTime;
    clock_gettime( CLOCK_REALTIME, &startTime );
 
    //
    // Parallel operations, timed.
    //
    float dotProduct = 0.0f;
 
    pthread_t  *threads = (pthread_t*)  malloc( nThreads * sizeof(pthread_t) );
    ThreadArgs *tArgs   = (ThreadArgs*) malloc( nThreads * sizeof(ThreadArgs) );
 
    // Launch threads (Steps 1 & 2 both done in parallel inside threadFunc).
    for( int t=0; t<nThreads; t++ )
    {
        tArgs[t].threadID = t;
        pthread_create( &threads[t], NULL, threadFunc, &tArgs[t] );
    }
 
    // Join all threads.
    for( int t=0; t<nThreads; t++ )
        pthread_join( threads[t], NULL );
 
    // Serial reduction of partial dot products
    for( int t=0; t<nThreads; t++ )
        dotProduct += partialDotProducts[t];
 
    printf( "Result of parallel calculation: %f\n", dotProduct );
 
    clock_gettime( CLOCK_REALTIME, &endTime );
    double seconds = (double)( endTime.tv_sec + 1e-9*endTime.tv_nsec - startTime.tv_sec - 1e-9*startTime.tv_nsec );
    printf( "Time for parallel calculations: %g secs.\n", seconds );
 
    // Serial check.
    for( int row=0; row<N; row++ )
    {
        v[row] = 0.0f;
        for( int col=0; col<N; col++ )
            v[row] += M[row][col] * u[col];
    }
 
    float dotProduct_serial = 0.0f;
    for( int i=0; i<N; i++ ) dotProduct_serial += v[i]*v[i];
 
    printf( "Result of the serial calculation: %f\n", dotProduct_serial );
 
    free( threads );
    free( tArgs );
    free( partialDotProducts );
    freeMatrixAndVector( N, M, u, v );
 
    return EXIT_SUCCESS;
}