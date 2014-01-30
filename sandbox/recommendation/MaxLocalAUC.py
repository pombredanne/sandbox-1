
import numpy 
import logging
import multiprocessing 
import sppy 
import time
from math import exp
from sandbox.util.SparseUtils import SparseUtils
from sandbox.recommendation.MaxLocalAUCCython import derivativeUi, derivativeVi, updateVApprox, updateUApprox, objectiveApprox, localAUCApprox
from apgl.util.Sampling import Sampling 
from apgl.util.Util import Util 

class MaxLocalAUC(object): 
    """
    Let's try different ways of maximising the local AUC with a penalty term. 
    """
    def __init__(self, lmbda, k, r, sigma=0.05, eps=0.1, stochastic=False): 
        self.lmbda = lmbda
        self.k = k 
        self.r = r
        self.sigma = sigma
        self.eps = eps 
        self.stochastic = stochastic
        
        #Optimal rate doesn't seem to work 
        self.rate = "constant"
        self.alpha = 0.000002
        self.t0 = 100
        
        self.recordStep = 10

        self.pythonDerivative = False 
        self.approxDerivative = True 
        
        self.numRowSamples = 10
        self.numAucSamples = 100
        self.maxIterations = 100
        
        self.iterationsPerUpdate = 10
        
        self.initialAlg = "rand"
        
        #Model selection parameters 
        self.folds = 3 
        self.ks = numpy.array([10, 20, 50])
        self.lmbdas = numpy.array([10**-7, 10**-6, 10**-5, 10**-4]) 
    

    
    def getOmegaList(self, X): 
        """
        Return a list such that the ith element contains an array of nonzero 
        entries in the ith row of X. 
        """
        omegaList = []
        
        for i in range(X.shape[0]): 
            omegaList.append(numpy.array(X[i, :].nonzero()[1], numpy.uint))
        return omegaList 
    
    def learnModel(self, X, verbose=False): 
        """
        Max local AUC with Frobenius norm penalty. Solve with gradient descent. 
        The input is a sparse array. 
        """
        
        m = X.shape[0]
        n = X.shape[1]
        omegaList = self.getOmegaList(X)
  
        if self.initialAlg == "rand": 
            U = numpy.random.rand(m, self.k)
            V = numpy.random.rand(n, self.k)
        elif self.initialAlg == "ones": 
            U = numpy.ones((m, self.k))
            V = numpy.ones((n, self.k))
        elif self.initialAlg == "svd":
            logging.debug("Initialising with SVD")
            try: 
                U, s, V = SparseUtils.svdPropack(X, self.k)
            except ImportError: 
                U, s, V = SparseUtils.svdArpack(X, self.k)
            U = numpy.ascontiguousarray(U)
            V = numpy.ascontiguousarray(V)
        else:
            raise ValueError("Unknown initialisation: " + str(self.initialAlg))
        
        lastU = U+numpy.ones((m, self.k))*self.eps
        lastV = V+numpy.ones((n, self.k))*self.eps 
        
        normDeltaU = numpy.linalg.norm(U - lastU)
        normDeltaV = numpy.linalg.norm(V - lastV)
        objs = []
        aucs = []
        
        ind = 0
        eps = self.eps 

        #Convert to a csarray for faster access 
        logging.debug("Converting to csarray")
        X2 = sppy.csarray(X.shape, storagetype="row")
        X2[X.nonzero()] = X.data
        X2.compress()
        X = X2
        
        startTime = time.time()
    
        while (normDeltaU > eps or normDeltaV > eps) and ind < self.maxIterations: 
            lastU = U.copy() 
            lastV = V.copy() 
            
            if self.rate == "constant": 
                sigma = self.sigma 
            elif self.rate == "optimal":
                sigma = 1/(self.alpha*(self.t0 + ind))
                logging.debug("sigma=" + str(sigma))
            else: 
                raise ValueError("Invalid rate: " + self.rate)

            updateUApprox(X, U, V, omegaList, self.numAucSamples, self.sigma, self.iterationsPerUpdate, self.k, self.lmbda, self.r)
            updateVApprox(X, U, V, omegaList, self.numAucSamples, self.sigma, self.iterationsPerUpdate, self.k, self.lmbda, self.r)
            #self.updateV2(X, U, V, omegaList)

            normDeltaU = numpy.linalg.norm(U - lastU)
            normDeltaV = numpy.linalg.norm(V - lastV)               
                
            if ind % self.recordStep == 0: 
                objs.append(objectiveApprox(X, U, V, omegaList, self.numAucSamples, self.lmbda, self.r))
                aucs.append(localAUCApprox(X, U, V, omegaList, self.numAucSamples, self.r))
                printStr = "Iteration: " + str(ind)
                printStr += " local AUC~" + str(aucs[-1]) + " objective~" + str(objs[-1])
                printStr += " ||dU||=" + str(normDeltaU) + " " + "||dV||=" + str(normDeltaV)
                logging.debug(printStr)
            
            ind += 1
            
        totalTime = time.time() - startTime
        logging.debug("||dU||=" + str(normDeltaU) + " " + "||dV||=" + str(normDeltaV))
        logging.debug("Total time taken " + str(totalTime))
                        
        if verbose:     
            return U, V, numpy.array(objs), numpy.array(aucs), ind, totalTime
        else: 
            return U, V
        
    def derivativeU(self, X, U, V, omegaList): 
        """
        Find the derivative for all of U. 
        """
        
        if not self.stochastic: 
            inds = numpy.arange(X.shape[0])
        else: 
            inds = numpy.random.randint(0, X.shape[0], self.numRowSamples)
        
        dU = numpy.zeros((inds.shape[0], self.k))        
        
        if self.pythonDerivative: 
            for j in range(inds.shape[0]): 
                i = inds[j]
                dU[j, :] = self.derivativeUi(X, U, V, omegaList, i)
        else:
            if self.approxDerivative: 
                dU = derivativeUApprox(X, U, V, omegaList, inds, self.numAucSamples, self.k, self.lmbda, self.r) 
            else:    
                for j in range(inds.shape[0]): 
                    i = inds[j]
                    dU[j, :] = derivativeUi(X, U, V, omegaList, i, self.k, self.lmbda, self.r)
            
        return dU, inds 
        
    #@profile
    def derivativeUi(self, X, U, V, omegaList, i): 
        """
        delta phi/delta u_i
        """
        m = X.shape[0]
        deltaPhi = self.lmbda * U[i, :]
        
        omegai = omegaList[i]
        omegaBari = numpy.setdiff1d(numpy.arange(X.shape[1]), omegai)
        
        deltaAlpha = numpy.zeros(self.k)
        
        ui = U[i, :]
        
        for p in omegai: 
            vp = V[p, :]
            uivp = ui.dot(vp)
            kappa = exp(-uivp +self.r[i])
            onePlusKappa = 1+kappa
            onePlusKappaSq = onePlusKappa**2
            
            for q in omegaBari: 
                vq = V[q, :]
                uivq = ui.dot(vq)
                gamma = exp(-uivp+uivq)
                onePlusGamma = 1+gamma
                onePlusGammaSq = onePlusGamma**2
                
                denom = onePlusGammaSq * onePlusKappaSq
                denom2 = onePlusGammaSq * onePlusKappa
                deltaAlpha += vp*((gamma+kappa+2*gamma*kappa)/denom) - vq*(gamma/denom2) 
                
        if omegai.shape[0] * omegaBari.shape[0] != 0: 
            deltaAlpha /= float(omegai.shape[0] * omegaBari.shape[0]*m)
            
        deltaPhi -= deltaAlpha
        
        return deltaPhi
        
    def updateV(self, X, U, V, omegaList): 
        """
        Find the derivative with respect to V or part of it. 
        """
        if not self.stochastic: 
            inds = numpy.arange(X.shape[1])
        else: 
            pass 
                    
        for j in range(inds.shape[0]): 
            i = inds[j]
            dV = self.derivativeVi2(X, U, V, omegaList, i)
            V[i, :] -= self.sigma*dV

    #@profile    
    def updateV2(self, X, U, V, omegaList): 
        """
        delta phi/delta v_j
        """
        inds = numpy.random.randint(0, X.shape[1], self.iterationsPerUpdate)
        for j in inds:
            m = X.shape[0]
            deltaTheta = self.lmbda*m * V[j, :]
             
            for i in range(X.shape[0]): 
                omegai = omegaList[i]
                
                deltaBeta = numpy.zeros(self.k) 
                ui = U[i, :]
                
                if X[i, j] != 0: 
                    omegaBari = numpy.setdiff1d(numpy.arange(X.shape[1]), omegai)
                    
                    p = j 
                    vp = V[p, :]
                    uivp = ui.dot(vp)
                    kappa = exp(-uivp + self.r[i])
                    onePlusKappa = 1+kappa
                    
                    for q in omegaBari: 
                        uivq = ui.dot(V[q, :])
                        gamma = exp(-uivp+uivq)
                        onePlusGamma = 1+gamma
                        
                        denom = onePlusGamma**2 * onePlusKappa**2
                        deltaBeta += ui*(gamma+kappa+2*gamma*kappa)/denom
                else:
                    q = j 
                    vq = V[q, :]
                    uivq = ui.dot(vq)
                    
                    for p in omegai: 
                        uivp = ui.dot(V[p, :])
                        
                        gamma = exp(-uivp+uivq)
                        kappa = exp(-uivp+self.r[i])
                        
                        deltaBeta += -ui* gamma/((1+gamma)**2 * (1+kappa))
                
                numOmegai = omegai.shape[0]       
                numOmegaBari = X.shape[1]-numOmegai
                
                if numOmegai*numOmegaBari != 0: 
                    deltaBeta /= float(numOmegai*numOmegaBari)
                    
                deltaTheta -= deltaBeta 
            
            deltaTheta /= float(m)
            
            V[j, :] -= self.sigma*deltaTheta


    def derivativeVi2(self, X, U, V, omegaList, j): 
        """
        delta phi/delta v_j
        """
        m = X.shape[0]
        deltaTheta = self.lmbda*m * V[j, :]
        
        inds = numpy.unique(numpy.random.randint(m, size=100))
        numAucSamples = 5
         
        for i in inds: 
            omegai = omegaList[i]
            numOmegai = omegai.shape[0]       
            numOmegaBari = X.shape[1]-numOmegai
            
            deltaBeta = numpy.zeros(self.k) 
            ui = U[i, :]
            
            if X[i, j] != 0: 
                omegaBari = numpy.setdiff1d(numpy.arange(X.shape[1]), omegai)
                omegaBari = numpy.random.choice(omegaBari, numAucSamples)
                
                p = j 
                vp = V[p, :]
                uivp = ui.dot(vp)
                kappa = exp(-uivp + self.r[i])
                onePlusKappa = 1+kappa
                
                for q in omegaBari: 
                    uivq = ui.dot(V[q, :])
                    gamma = exp(-uivp+uivq)
                    onePlusGamma = 1+gamma
                    
                    denom = onePlusGamma**2 * onePlusKappa**2
                    deltaBeta += ui*(gamma+kappa+2*gamma*kappa)/denom
                    deltaBeta /= float(numAucSamples*numOmegai)
            else:
                q = j 
                vq = V[q, :]
                uivq = ui.dot(vq)
                
                omegai2 = numpy.random.choice(omegai, numAucSamples)                
                
                for p in omegai2: 
                    uivp = ui.dot(V[p, :])
                    
                    gamma = exp(-uivp+uivq)
                    kappa = exp(-uivp+self.r[i])
                    
                    deltaBeta += -ui* gamma/((1+gamma)**2 * (1+kappa))
                    deltaBeta /= float(numAucSamples*(X.shape[1]-numOmegai))
                
            deltaTheta -= deltaBeta 
        deltaTheta /= float(inds.shape[0])
        
        return deltaTheta

    def localAUC(self, X, U, V, omegaList): 
        """
        Compute the local AUC for the score functions UV^T relative to X with 
        quantile vector r. 
        """
        #For now let's compute the full matrix 
        Z = U.dot(V.T)
        
        localAuc = numpy.zeros(X.shape[0]) 
        allInds = numpy.arange(X.shape[1])
        
        for i in range(X.shape[0]): 
            omegai = omegaList[i]
            omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
            
            if omegai.shape[0] * omegaBari.shape[0] != 0: 
                partialAuc = 0                
                
                for p in omegai: 
                    for q in omegaBari: 
                        if Z[i, p] > Z[i, q] and Z[i, p] > self.r[i]: 
                            partialAuc += 1 
                            
                localAuc[i] = partialAuc/float(omegai.shape[0] * omegaBari.shape[0])
        
        localAuc = localAuc.mean()        
        
        return localAuc

    def localAUCApprox(self, X, U, V, omegaList): 
        """
        Compute the estimated local AUC for the score functions UV^T relative to X with 
        quantile vector r. 
        """
        #For now let's compute the full matrix 
        Z = U.dot(V.T)
        
        localAuc = numpy.zeros(X.shape[0]) 
        allInds = numpy.arange(X.shape[1])

        for i in range(X.shape[0]): 
            omegai = omegaList[i]
            omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
            
            if omegai.shape[0] * omegaBari.shape[0] != 0: 
                partialAuc = 0 

                for j in range(self.numAucSamples):
                    ind = numpy.random.randint(omegai.shape[0]*omegaBari.shape[0])
                    p = omegai[int(ind/omegaBari.shape[0])] 
                    q = omegaBari[ind % omegaBari.shape[0]]   
                    
                    if Z[i, p] > Z[i, q] and Z[i, p] > self.r[i]: 
                        partialAuc += 1 
                            
                localAuc[i] = partialAuc/float(self.numAucSamples)
            
        localAuc = localAuc.mean()        
        
        return localAuc
    
    #@profile
    def objective(self, X, U, V, omegaList):         
        obj = 0 
        m = X.shape[0]
        
        allInds = numpy.arange(X.shape[1])        
        
        for i in range(X.shape[0]): 
            omegai = omegaList[i]
            omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
            
            ui = U[i, :]       
            uiV = ui.dot(V.T)
            ri = self.r[i]
            
            if omegai.shape[0] * omegaBari.shape[0] != 0: 
                partialAuc = 0                
                
                for p in omegai: 
                    uivp = uiV[p]
                    kappa = numpy.exp(-uivp+ri)
                    onePlusKappa = 1+kappa
                    
                    for q in omegaBari: 
                        uivq = uiV[q]
                        gamma = exp(-uivp+uivq)

                        partialAuc += 1/((1+gamma) * onePlusKappa)
                            
                obj += partialAuc/float(omegai.shape[0] * omegaBari.shape[0])
        
        obj /= m       
        obj = 0.5*self.lmbda * (numpy.sum(U**2) + numpy.sum(V**2)) - obj
        
        return obj 

    #@profile
    def objectiveApprox(self, X, U, V, omegaList):         
        obj = 0 
        m = X.shape[0]
        
        allInds = numpy.arange(X.shape[1])        
        
        for i in range(X.shape[0]): 
            omegai = omegaList[i]
            omegaBari = numpy.setdiff1d(allInds, omegai, assume_unique=True)
            
            ui = U[i, :]       
            uiV = ui.dot(V.T)
            ri = self.r[i]
            
            if omegai.shape[0] * omegaBari.shape[0] != 0: 
                partialAuc = 0                
                
                indsP = numpy.random.randint(0, omegai.shape[0], self.numAucSamples)  
                indsQ = numpy.random.randint(0, omegaBari.shape[0], self.numAucSamples)
                
                for j in range(self.numAucSamples):                    
                    p = omegai[indsP[j]] 
                    q = omegaBari[indsQ[j]]                  
                
                    uivp = uiV[p]
                    kappa = exp(-uivp+ri)
                    
                    uivq = uiV[q]
                    gamma = exp(-uivp+uivq)

                    partialAuc += 1/((1+gamma) * 1+kappa)
                            
                obj += partialAuc/float(self.numAucSamples)
        
        obj /= m       
        obj = 0.5*self.lmbda * (numpy.sum(U**2) + numpy.sum(V**2)) - obj
        
        return obj 
        
    def modelSelect(self, X): 
        """
        Perform model selection on X and return the best parameters. 
        """
        cvInds = Sampling.randCrossValidation(self.folds, X.nnz)
        localAucs = numpy.zeros((self.ks.shape[0], self.lmbdas.shape[0], len(cvInds)))
        
        logging.debug("Performing model selection")
        for icv, (trainInds, testInds) in enumerate(cvInds):
            Util.printIteration(icv, 1, self.folds, "Fold: ")

            trainX = SparseUtils.submatrix(X, trainInds)
            testX = SparseUtils.submatrix(X, testInds)
            
            for i, k in enumerate(self.ks): 
                for j, lmbda in enumerate(self.lmbdas): 
                    self.k = k 
                    self.lmbda = lmbda 
                    
                    U, V = self.learnModel(trainX)
                    
                    omegaList = self.getOmegaList(testX)
                    localAucs[i, j, icv] = self.localAUCApprox(testX, U, V, omegaList)
        
        meanLocalAucs = numpy.mean(localAucs, 2)
        stdLocalAucs = numpy.std(localAucs, 2)
        
        logging.debug(meanLocalAucs)
        
        k = self.ks[numpy.unravel_index(numpy.argmax(meanLocalAucs), meanLocalAucs.shape)[0]]
        lmbda = self.lmbdas[numpy.unravel_index(numpy.argmax(meanLocalAucs), meanLocalAucs.shape)[1]]
        
        logging.debug("Model parameters: k=" + str(k) + " lambda=" + str(lmbda))
        
        self.k = k 
        self.lmbda = lmbda 