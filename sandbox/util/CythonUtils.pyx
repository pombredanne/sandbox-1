#cython: profile=True 
#cython: boundscheck=False
#cython: wraparound=False
#cython: nonecheck=False
import cython
cimport numpy
import numpy

from libc.stdlib cimport rand
cdef extern from "limits.h":
    int RAND_MAX

cdef extern from "math.h":
    double exp(double x)
    bint isnan(double x)  
    double sqrt(double x)

cdef inline int randint(int i):
    """
    Note that i must be less than RAND_MAX. 
    """
    return rand() % i   


cdef inline double square(double d):
    """
    Find the square of the input double. 
    """
    return d*d    


cdef inline double dot(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, numpy.ndarray[double, ndim = 2, mode="c"] V, unsigned int j, unsigned int k):
    """
    Compute the dot product between U[i, :] and V[j, :]
    """
    cdef double result = 0
    cdef unsigned int s = 0
    cdef double e1, e2
    for s in range(k):
        e1 = U[i, s]
        e2 = V[j, s]
        result += e1*e2
    return result


cdef inline double normRow(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, unsigned int k):
    """
    Compute the dot product between U[i, :] and V[j, :]
    """
    cdef double result = 0
    cdef unsigned int s = 0
    for s in range(k):
        result += square(U[i, s])

    return sqrt(result)

cdef numpy.ndarray[double, ndim = 1, mode="c"] scale(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, double d, unsigned int k):
    """
    Computes U[i, :] * d where k is U.shape[1]
    """
    cdef numpy.ndarray[double, ndim = 1, mode="c"] ui = numpy.empty(k)
    cdef unsigned int s = 0
    for s in range(k):
        ui[s] = U[i, s]*d
    return ui

cdef inline numpy.ndarray[double, ndim = 1, mode="c"] plusEquals(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, numpy.ndarray[double, ndim = 1, mode="c"] d, unsigned int k):
    """
    Computes U[i, :] += d[i] where k is U.shape[1]
    """
    cdef unsigned int s = 0
    for s in range(k):
        U[i, s] = U[i, s] + d[s]

cdef inline numpy.ndarray[double, ndim = 1, mode="c"] plusEquals1d(numpy.ndarray[double, ndim = 1, mode="c"] u, numpy.ndarray[double, ndim = 1, mode="c"] d, unsigned int k):
    """
    Computes U[i] += d[i] 
    """
    cdef unsigned int s = 0
    for s in range(k):
        u[s] = u[s] + d[s]

cdef unsigned int getNonZeroRow(X, unsigned int i, unsigned int n):
    """
    Find a random nonzero element in the ith row of X
    """
    cdef unsigned int q = numpy.random.randint(0, n)
    
    while X[i, q] != 0:
        q = numpy.random.randint(0, n)
    return q

cdef unsigned int inverseChoice(numpy.ndarray[int, ndim=1, mode="c"] v, unsigned int n):
    """
    Find a random nonzero element in the range 0:n not in v
    """
    cdef unsigned int q = numpy.random.randint(0, n)
    cdef int inV = 1
    cdef unsigned int j 
    cdef unsigned int m = v.shape[0]
    
    while inV == 1:
        q = numpy.random.randint(0, n)
        inV = 0 
        for j in range(m): 
            if q == v[j]: 
                inV = 1 
                break 
    return q
    
def inverseChoicePy(v, n): 
    return inverseChoice(v, n)
    
cdef numpy.ndarray[int, ndim=1, mode="c"] choice(numpy.ndarray[int, ndim=1, mode="c"] inds, unsigned int numSamples, numpy.ndarray[double, ndim=1, mode="c"] cumProbs):
    """
    Given a list of numbers in inds, and associated cumulative probabilties, pick numSample 
    elements according to the probabilities. Note that probabilties must sum to 
    1.
    """
    cdef numpy.ndarray[int, ndim=1, mode="c"] sampleArray = numpy.zeros(numSamples, numpy.int32)
    cdef double p 
    cdef unsigned int i, j
    
    for j in range(numSamples):
        p = numpy.random.rand()
        for i in range(cumProbs.shape[0]): 
            if cumProbs[i] > p: 
                break 
        sampleArray[j] = inds[i]
    
    return sampleArray

cdef numpy.ndarray[int, ndim=1, mode="c"] uniformChoice(numpy.ndarray[int, ndim=1, mode="c"] inds, unsigned int numSamples):
    """
    Given a list of numbers in inds, pick numSample elements uniformly randomly.
    """

    cdef numpy.ndarray[int, ndim=1, mode="c"] sampleArray = numpy.zeros(numSamples, numpy.int32)
    cdef double p 
    cdef unsigned int i, j
    
    for j in range(numSamples):
        i = numpy.random.randint(0, inds.shape[0])
        sampleArray[j] = inds[i]
    
    return sampleArray

def choicePy(inds, numSamples, probs): 
    return choice(inds, numSamples, probs)