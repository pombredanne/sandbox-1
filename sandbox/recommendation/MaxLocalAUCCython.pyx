# cython: profile=True 
import cython
from cython.parallel import parallel, prange
cimport numpy
import numpy
from sandbox.util.SparseUtilsCython import SparseUtilsCython

cdef extern from "math.h":
    double exp(double x)

@cython.profile(False)
cdef inline double square(double d):
    return d*d    

@cython.nonecheck(False)
@cython.boundscheck(False) 
@cython.wraparound(False) 
cdef inline double dot(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, numpy.ndarray[double, ndim = 2, mode="c"] V, unsigned int j, unsigned int k):
    """
    Compute the dot product between U[i, :] and V[j, :]
    """
    cdef double result = 0
    cdef unsigned int s = 0
    for s in range(k):
        result += U[i, s]*V[j, s]
    return result

@cython.boundscheck(False) 
@cython.wraparound(False) 
cdef inline numpy.ndarray[double, ndim = 1, mode="c"] scale(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, double d, unsigned int k):
    """
    Computes U[i, :] * d where k is U.shape[1]
    """
    cdef numpy.ndarray[double, ndim = 1, mode="c"] ui = numpy.empty(k)
    cdef unsigned int s = 0
    for s in range(k):
        ui[s] = U[i, s]*d
    return ui

@cython.boundscheck(False) 
@cython.wraparound(False) 
cdef inline numpy.ndarray[double, ndim = 1, mode="c"] plusEquals(numpy.ndarray[double, ndim = 2, mode="c"] U, unsigned int i, numpy.ndarray[double, ndim = 1, mode="c"] d, unsigned int k):
    """
    Computes U[i, :] += d[i] where k is U.shape[1]
    """
    cdef unsigned int s = 0
    for s in range(k):
        U[i, s] = U[i, s] + d[s]

@cython.boundscheck(False) 
@cython.wraparound(False) 
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

@cython.boundscheck(False)
def derivativeUi(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int i, numpy.ndarray[double, ndim=1, mode="c"] r, double nu): 
    """
    delta phi/delta u_i
    """
    cdef unsigned int p, q, m, n 
    cdef unsigned int k = U.shape[1]
    cdef double uivp, ri, uivq, kappa, onePlusKappa, onePlusKappaSq, gamma, onePlusGamma
    cdef double denom, denom2, alphaScale
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegaBari = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaAlpha = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaTheta = numpy.zeros(k, numpy.float)
    
    m = X.shape[0]
    n = X.shape[1]
    #deltaTheta = scale(U, i, lmbda, k) 
    
    omegai = omegaList[i]
    omegaBari = numpy.setdiff1d(numpy.arange(n, dtype=numpy.uint), omegai, assume_unique=True)
    
    deltaAlpha = numpy.zeros(k)
    ri = r[i]
    
    for p in omegai: 
        uivp = dot(U, i, V, p, k)
        kappa = exp(-uivp +ri)
        onePlusKappa = 1+kappa
        onePlusKappaSq = square(onePlusKappa)
        
        for q in omegaBari: 
            uivq = dot(U, i, V, q, k)
            gamma = exp(nu*(uivq - uivp))
            onePlusGamma = 1+gamma
            onePlusGammaSq = square(onePlusGamma)
            
            denom = onePlusGammaSq * onePlusKappaSq
            denom2 = onePlusGammaSq * onePlusKappa
            deltaAlpha += scale(V, p, (gamma+kappa+2*gamma*kappa)/denom, k) - scale(V, q, (gamma/denom2), k) 
            
    if omegai.shape[0] * omegaBari.shape[0] != 0: 
        deltaAlpha /= float(omegai.shape[0] * omegaBari.shape[0]*m)
        
    deltaTheta -= deltaAlpha
    normDeltaTheta = numpy.linalg.norm(deltaTheta)
    
    if normDeltaTheta != 0: 
        deltaTheta = deltaTheta/normDeltaTheta    
    
    return deltaTheta

def updateU(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, double sigma, numpy.ndarray[double, ndim=1, mode="c"] r, double nu): 
    """
    Compute the full gradient descent update of U
    """    
    
    cdef numpy.ndarray[numpy.float_t, ndim=2, mode="c"] dU = numpy.zeros((U.shape[0], U.shape[1]), numpy.float)
    cdef unsigned int i 
    cdef unsigned int m = X.shape[0]
    cdef unsigned int k = U.shape[1]
    
    for i in range(m): 
        dU[i, :] = derivativeUi(X, U, V, omegaList, i, r, nu) 
    
    U -= sigma*dU
    
    for i in range(m):
        U[i,:] = scale(U, i, 1/numpy.linalg.norm(U[i,:]), k)   

@cython.boundscheck(False)
@cython.wraparound(False)
def derivativeUiApprox(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int i, unsigned int numRowSamples, unsigned int numAucSamples, numpy.ndarray[double, ndim=1, mode="c"] r, double nu, double lmbda, double rho):
    """
    Find an approximation of delta phi/delta u_i
    """
    cdef unsigned int p, q, ind, j, s
    cdef unsigned int k = U.shape[1]
    cdef double uivp, ri, uivq, kappa, onePlusKappa, onePlusKappaSq, gamma, onePlusGamma
    cdef double denom, denom2, normDeltaBeta, alpha 
    cdef unsigned int m = X.shape[0], n = X.shape[1], numOmegai, numOmegaBari
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegaBari = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaAlpha = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaTheta = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.int_t, ndim=1, mode="c"] indsP = numpy.zeros(k, numpy.int)
    cdef numpy.ndarray[numpy.int_t, ndim=1, mode="c"] indsQ = numpy.zeros(k, numpy.int)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] rowUInds = numpy.unique(numpy.array(numpy.random.randint(0, m, numRowSamples), dtype=numpy.uint))
    
    #Penalise non orthogonal directions 
    rowUInds = numpy.union1d(rowUInds, numpy.array([i], dtype=numpy.uint)) 

    for j in rowUInds: 
        alpha +=  dot(U, i, U, j, k)
    alpha = (alpha - 2)/rowUInds.shape[0]

    deltaTheta = scale(U, i, lmbda, k)    
     
    omegai = omegaList[i]
    omegaBari = numpy.setdiff1d(numpy.arange(n, dtype=numpy.uint), omegai, assume_unique=True)
    numOmegai = omegai.shape[0]
    numOmegaBari = n-numOmegai
    
    deltaAlpha = numpy.zeros(k)
    ri = r[i]
    
    if numOmegai * numOmegaBari != 0: 
        indsP = numpy.random.randint(0, numOmegai, numAucSamples)
        indsQ = numpy.random.randint(0, numOmegaBari, numAucSamples)        
        
        for j in range(numAucSamples):
            p = omegai[indsP[j]] 
            q = omegaBari[indsQ[j]]  
        
            uivp = dot(U, i, V, p, k)
            kappa = exp(ri-uivp)
            onePlusKappa = 1+kappa
            onePlusKappaSq = square(onePlusKappa)
            
            uivq = dot(U, i, V, q, k)
            gamma = exp(nu*(uivq-uivp))
            onePlusGamma = 1+gamma
            onePlusGammaSq = square(onePlusGamma)
            
            denom = onePlusGammaSq * onePlusKappaSq
            denom2 = onePlusGammaSq * onePlusKappa
            if denom != 0 and denom2 != 0: 
                deltaAlpha += scale(V, p, ((gamma+kappa+2*gamma*kappa)/denom), k) - scale(V, q, (gamma/denom2), k) 
                
        deltaAlpha /= float(numAucSamples)
        deltaTheta -= deltaAlpha
    
    normDeltaTheta = numpy.linalg.norm(deltaTheta)
    
    if normDeltaTheta != 0: 
        deltaTheta = deltaTheta/normDeltaTheta
    
    return deltaTheta


@cython.boundscheck(False)
def derivativeVi(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int j, numpy.ndarray[double, ndim=1, mode="c"] r, double nu, double lmbda): 
    """
    delta phi/delta v_j
    """
    cdef unsigned int i = 0
    cdef unsigned int p, q, numOmegai, numOmegaBari
    cdef unsigned int m = X.shape[0]
    cdef unsigned int n = X.shape[1]
    cdef unsigned int k = U.shape[1]
    cdef double uivp, kappa, onePlusKappa, uivq, gamma, onePlusGamma, denom, ri, betaScale
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaTheta = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaAlpha = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaBeta = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] ui = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegaBari = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] allInds = numpy.arange(n, dtype=numpy.uint)
    
    deltaTheta = scale(V, j, lmbda, k)

    for i in range(m): 
        omegai = omegaList[i]
        
        deltaBeta = numpy.zeros(k) 
        betaScale = 0
        ui = U[i, :]
        ri = r[i]
        
        if X[i, j] != 0: 
            omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
            
            p = j 
            uivp = dot(U, i, V, p, k)
            kappa = exp(-uivp+ri)
            onePlusKappa = 1+kappa
            onePlusKappaSq = onePlusKappa**2
            twoKappa = 2*kappa
            
            for q in omegaBari: 
                uivq = dot(U, i, V, q, k)
                gamma = exp(nu*(uivq - uivp))
                onePlusGamma = 1+gamma
                
                denom = onePlusGamma**2 * onePlusKappaSq 
                betaScale += ((gamma+kappa+gamma*twoKappa)/denom)
                
            deltaBeta = scale(U, i, betaScale, k)
        else:
            q = j 
            uivq = dot(U, i, V, q, k)
            
            for p in omegai: 
                uivp = dot(U, i, V, p, k)
                
                gamma = exp(nu*(uivq - uivp))
                kappa = exp(-uivp+ri)
                
                betaScale -= (gamma/((1+gamma)**2 * (1+kappa)))
                
            deltaBeta = scale(U, i, betaScale, k)
        
        numOmegai = omegai.shape[0]       
        numOmegaBari = n-numOmegai
        
        if numOmegai*numOmegaBari != 0: 
            deltaBeta /= float(numOmegai*numOmegaBari)
            
        deltaAlpha += deltaBeta 
    
    deltaAlpha /= float(m)
    deltaTheta -= deltaAlpha
    deltaTheta = deltaTheta/numpy.linalg.norm(deltaTheta)
    
    return deltaTheta
 

def updateV(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, double sigma, numpy.ndarray[double, ndim=1, mode="c"] r, double nu, double lmbda): 
    """
    Compute the full gradient descent update of V
    """
    cdef numpy.ndarray[numpy.float_t, ndim=2, mode="c"] dV = numpy.zeros((V.shape[0], V.shape[1]), numpy.float)
    cdef unsigned int i 
    cdef unsigned int n = X.shape[1]
    cdef unsigned int k = V.shape[1]
    
    for i in range(n): 
        dV[i, :] = derivativeVi(X, U, V, omegaList, i, r, nu, lmbda) 
    
    V -= sigma*dV

    #for i in range(n):
    #    V[i,:] = scale(V, i, 1/numpy.linalg.norm(V[i,:]), k)   
       
   
@cython.boundscheck(False)
@cython.wraparound(False)
def derivativeViApprox(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int j, unsigned int numRowSamples, unsigned int numAucSamples, numpy.ndarray[double, ndim=1, mode="c"] r, double nu, double lmbda, double rho): 
    """
    delta phi/delta v_i
    """
    cdef unsigned int i = 0
    cdef unsigned int k = U.shape[1]
    cdef unsigned int p, q, numOmegai, numOmegaBari, t
    cdef unsigned int m = X.shape[0]
    cdef unsigned int n = X.shape[1], ind
    cdef unsigned int s = 0
    cdef double uivp, kappa, onePlusKappa, uivq, gamma, onePlusGamma, denom, riExp, uivpExp, betaScale, uivqExp, onePlusTwoKappa, ri, alpha
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaBeta = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] deltaTheta = numpy.zeros(k, numpy.float)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(k, numpy.uint)
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] rowInds = numpy.unique(numpy.array(numpy.random.randint(0, m, numRowSamples), dtype=numpy.uint))
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] rowVInds = numpy.unique(numpy.array(numpy.random.randint(0, n, numRowSamples), dtype=numpy.uint))
    
    #Penalise non orthogonal directions using rho*||V^T V - I||^2_F
    rowVInds = numpy.union1d(rowVInds, numpy.array([j], dtype=numpy.uint))

    for i in rowVInds: 
        alpha +=  dot(V, j, V, i, k)
    alpha = (alpha - 2)/rowVInds.shape[0]
    
    deltaTheta = scale(V, j, lmbda + rho*alpha, k)     
     
    for i in rowInds: 
        omegai = omegaList[i]
        numOmegai = omegai.shape[0]       
        numOmegaBari = n-numOmegai
        
        ri = r[i]
        betaScale = 0
        deltaBeta = numpy.zeros(k, numpy.float)
        
        if X[i, j] != 0:                 
            p = j 
            uivp = dot(U, i, V, p, k)

            kappa = exp(ri - uivp)
            onePlusKappa = 1+kappa
            onePlusTwoKappa = 1+kappa*2
            
            for s in range(numAucSamples): 
                q = getNonZeroRow(X, i, n)
            
                uivq = dot(U, i, V, q, k)
                gamma = exp(nu*(uivq - uivp)) #Faster to do this                     
                
                denom = square(1+gamma)
                betaScale += (kappa+gamma*onePlusTwoKappa)/denom
            #Note we  use numAucSamples*numOmegai to normalise
            deltaBeta = scale(U, i, betaScale/(numAucSamples*numOmegai*square(onePlusKappa)), k)
        else:
            q = j 
            uivq = dot(U, i, V, q, k)
            #uivqExp = exp(uivq) 
                            
            for p in omegai: 
                uivp = dot(U, i, V, p, k)
                
                gamma = exp(nu*(uivq - uivp))
                kappa = exp(ri - uivp)
                
                betaScale += gamma/(square(1+gamma) * (1+kappa))
            #Note we use numOmegaBari*numOmegai to normalise
            if numOmegai != 0:
                deltaBeta = scale(U, i, -betaScale/(numOmegai*numOmegaBari), k)             
        
        plusEquals1d(deltaTheta, -deltaBeta, k)
    
    #Normalise gradient vector 
    deltaTheta = deltaTheta/rowInds.shape[0]
    deltaTheta = deltaTheta/numpy.linalg.norm(deltaTheta)
    
    return deltaTheta

@cython.boundscheck(False)
@cython.wraparound(False)
def updateUVApprox(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, numpy.ndarray[unsigned int, ndim=1, mode="c"] rowInds, numpy.ndarray[unsigned int, ndim=1, mode="c"] colInds, unsigned int ind, double sigma, unsigned int numIterations, unsigned int numRowSamples, unsigned int numAucSamples, double w, double nu, double lmbda, double rho): 
    cdef unsigned int m = X.shape[0]
    cdef unsigned int n = X.shape[1]    
    cdef unsigned int k = U.shape[1] 
    cdef unsigned int numAucSamplesR = 100
    #cdef numpy.ndarray[double, ndim=1, mode="c"] r = numpy.ones(m)*-1
    cdef numpy.ndarray[double, ndim=1, mode="c"] r = SparseUtilsCython.computeR(U, V, w, numAucSamplesR) 
    cdef unsigned int i, j, s
    
    for s in range(numIterations):
        i = rowInds[(ind + s) % m]
        dUi = derivativeUiApprox(X, U, V, omegaList, i, numRowSamples, numAucSamples, r, nu, lmbda, rho)
        #dUi = derivativeUi(X, U, V, omegaList, i, r, nu)
        
        j = colInds[(ind + s) % n]
        dVj = derivativeViApprox(X, U, V, omegaList, j, numRowSamples, numAucSamples, r, nu, lmbda, rho)
        #dVi = derivativeVi(X, U, V, omegaList, j, r, nu)

        plusEquals(U, i, -sigma*dUi, k)
        
        normUi = numpy.linalg.norm(U[i,:])
        if normUi != 0: 
            U[i,:] = scale(U, i, 1/normUi, k)             
        
        plusEquals(V, j, -sigma*dVj, k)  
        
        #Note that we are penalising the norm of V in this derivative, however 
        #we renormalise to reduce instabilities in r. 
        normVj = numpy.linalg.norm(V[j,:])
        if normVj != 0: 
            V[j,:] = scale(V, j, 1/normVj, k)  
        
    
def objectiveApprox(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int numAucSamples, numpy.ndarray[double, ndim=1, mode="c"] r):         
    cdef double obj = 0 
    cdef unsigned int m = X.shape[0]
    cdef unsigned int n = X.shape[1]
    cdef unsigned int i, j, k, p, q
    cdef double kappa, onePlusKappa, uivp, uivq, gamma, partialAuc
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(10, numpy.uint)  
    cdef numpy.ndarray[numpy.int_t, ndim=1, mode="c"] indsP
    
    k = U.shape[1]
    
    for i in range(m): 
        omegai = omegaList[i]
        #omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
        
        ri = r[i]
        
        if omegai.shape[0] * (n-omegai.shape[0]) != 0: 
            partialAuc = 0                
            
            indsP = numpy.random.randint(0, omegai.shape[0], numAucSamples)  
            #indsQ = numpy.random.randint(0, omegaBari.shape[0], numAucSamples)
            
            for j in range(numAucSamples):
                p = omegai[indsP[j]] 
                #q = omegaBari[indsQ[j]]
                q = getNonZeroRow(X, i, n)                  
            
                uivp = dot(U, i, V, p, k)
                kappa = exp(-uivp+ri)
                
                uivq = dot(U, i, V, q, k)
                gamma = exp(-uivp+uivq)

                partialAuc += 1/((1+gamma) * (1+kappa))
                        
            obj += partialAuc/float(numAucSamples)
    
    obj /= m       
    obj = -obj
    
    return obj 
    
def localAUCApprox(X, numpy.ndarray[double, ndim=2, mode="c"] U, numpy.ndarray[double, ndim=2, mode="c"] V, list omegaList, unsigned int numAucSamples, numpy.ndarray[double, ndim=1, mode="c"] r): 
    """
    Compute the estimated local AUC for the score functions UV^T relative to X with 
    quantile vector r. 
    """
    
    cdef unsigned int m = X.shape[0]
    cdef unsigned int n = X.shape[1]
    cdef numpy.ndarray[numpy.uint_t, ndim=1, mode="c"] omegai = numpy.zeros(10, numpy.uint)
    cdef numpy.ndarray[numpy.float_t, ndim=1, mode="c"] localAucArr = numpy.zeros(m)
    cdef unsigned int i, j, k, ind, p, q
    cdef double partialAuc, ri

    k = U.shape[1]

    for i in range(m): 
        omegai = omegaList[i]
        #omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
        ri = r[i]
        
        if omegai.shape[0] * (n-omegai.shape[0]) != 0: 
            partialAuc = 0                
            
            for j in range(numAucSamples):
                ind = numpy.random.randint(omegai.shape[0])
                p = omegai[ind] 
                
                #ind = numpy.random.randint(omegaBari.shape[0])
                #q = omegaBari[ind]   
                q = getNonZeroRow(X, i, n)                
                
                if dot(U, i, V, p, k) > dot(U, i, V, q, k) and dot(U, i, V, p, k) > ri: 
                    partialAuc += 1 
                        
            localAucArr[i] = partialAuc/float(numAucSamples)     
    
    return localAucArr.mean()