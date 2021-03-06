import os
import sys
from sandbox.recommendation.MaxLocalAUC import MaxLocalAUC, restrictOmega
from sandbox.util.SparseUtils import SparseUtils
import numpy
import unittest
import logging
import numpy.linalg 
import numpy.testing as nptst 

class MaxLocalAUCTest(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        numpy.set_printoptions(precision=3, suppress=True, linewidth=150)
        
        numpy.seterr(all="raise")
        numpy.random.seed(22)
    
    @unittest.skip("")
    def testLearnModel(self): 
        m = 50 
        n = 20 
        k = 5 
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, csarray=True)

        u = 0.1
        w = 1-u
        eps = 0.05
        
        maxLocalAuc = MaxLocalAUC(k, w, alpha=5.0, eps=eps, stochastic=False)
        U, V = maxLocalAuc.learnModel(X)
        
        maxLocalAuc.stochastic = True 
        U, V = maxLocalAuc.learnModel(X)
        
        #Test case where we do not have validation set 
        maxLocalAuc.validationUsers = 0.0
        U, V = maxLocalAuc.learnModel(X)


    @unittest.skip("")
    def testParallelLearnModel(self): 
        numpy.random.seed(21)
        m = 500 
        n = 200 
        k = 5 
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, csarray=True)
        
        from wallhack.rankingexp.DatasetUtils import DatasetUtils
        X, U, V = DatasetUtils.syntheticDataset1()

        
        u = 0.1
        w = 1-u
        eps = 0.05
        maxLocalAuc = MaxLocalAUC(k, w, alpha=1.0, eps=eps, stochastic=True)
        maxLocalAuc.maxIterations = 3
        maxLocalAuc.recordStep = 1
        maxLocalAuc.rate = "optimal"
        maxLocalAuc.t0 = 2.0
        maxLocalAuc.validationUsers = 0.0
        maxLocalAuc.numProcesses = 4
        
        os.system('taskset -p 0xffffffff %d' % os.getpid())
        print(X.nnz/maxLocalAuc.numAucSamples)
        U, V = maxLocalAuc.parallelLearnModel(X)


    @unittest.skip("")
    def testModelSelectMaxNorm(self): 
        m = 10 
        n = 20 
        k = 5 
        
        u = 0.5
        w = 1-u
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, w, csarray=True)
        
        os.system('taskset -p 0xffffffff %d' % os.getpid())
        
        eps = 0.001
        k = 5
        maxLocalAuc = MaxLocalAUC(k, w, eps=eps, stochastic=True)
        maxLocalAuc.maxIterations = 5
        maxLocalAuc.recordStep = 1
        maxLocalAuc.validationSize = 3
        maxLocalAuc.metric = "f1"
        
        maxLocalAuc.modelSelectNorm(X)

           
    @unittest.skip("")
    def testModelSelectLmbda(self): 
        m = 10 
        n = 20 
        k = 5 
        
        u = 0.5
        w = 1-u
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, w, csarray=True)
        
        os.system('taskset -p 0xffffffff %d' % os.getpid())
        
        eps = 0.001
        k = 5
        maxLocalAuc = MaxLocalAUC(k, w, eps=eps, stochastic=True)
        maxLocalAuc.maxIterations = 5
        maxLocalAuc.recordStep = 1
        maxLocalAuc.validationSize = 3
        maxLocalAuc.metric = "f1"
        maxLocalAuc.rate = "constant"
        maxLocalAuc.ks = numpy.array([4, 8])
        maxLocalAuc.modelSelectLmbda(X)
        

    @unittest.skip("")
    def testLearningRateSelect(self): 
        m = 10 
        n = 20 
        k = 5 
        
        u = 0.5
        w = 1-u
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, w, csarray=True)
        
        eps = 0.001
        maxLocalAuc = MaxLocalAUC(k, u, eps=eps, stochastic=True)
        maxLocalAuc.rate = "optimal"
        maxLocalAuc.maxIterations = 5
        maxLocalAuc.numProcesses = 1
        
        maxLocalAuc.learningRateSelect(X)

    def testStr(self): 
        k=10
        u= 0.1
        eps = 0.001
        maxLocalAuc = MaxLocalAUC(k, u, eps=eps)    
        

    def testCopy(self): 
        u= 0.1
        eps = 0.001
        k = 10 
        maxLocalAuc = MaxLocalAUC(k, u, alpha=5.0, eps=eps)
        maxLocalAuc.copy()


    def testRestrictOmega(self):
        m = 50 
        n = 100 
        k = 5 
        
        u = 0.5
        w = 1-u
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, w, csarray=True)
        
        indPtr, colInds = SparseUtils.getOmegaListPtr(X)
        runs = 100 
        
        for i in range(runs): 
            colSubset = numpy.random.choice(n, 20, replace=False)
    
            newIndPtr, newColInds = restrictOmega(indPtr, colInds, colSubset)
            
            for i in range(m): 
                omegai = colInds[indPtr[i]:indPtr[i+1]]
                omegai2 = newColInds[newIndPtr[i]:newIndPtr[i+1]]
                
                a = numpy.setdiff1d(omegai, omegai2)
                self.assertEquals(numpy.intersect1d(a, colSubset).shape[0], 0)
            
    def testOverfit(self): 
        """
        See if we can get a zero objective on the hinge loss 
        """
        m = 10 
        n = 20 
        k = 5 
        
        u = 0.5
        w = 1-u
        X = SparseUtils.generateSparseBinaryMatrix((m, n), k, w, csarray=True)
        
        eps = 0.001
        k = 10
        maxLocalAuc = MaxLocalAUC(k, u, eps=eps, stochastic=True)
        maxLocalAuc.rate = "constant"
        maxLocalAuc.maxIterations = 500
        maxLocalAuc.numProcesses = 1
        maxLocalAuc.loss = "hinge"
        maxLocalAuc.validationUsers = 0
        maxLocalAuc.lmbda = 0        
        
        print("Overfit example")
        U, V, trainMeasures, testMeasures, iterations, time = maxLocalAuc.learnModel(X, verbose=True)
        
        self.assertAlmostEquals(trainMeasures[-1, 0], 0, 3)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()