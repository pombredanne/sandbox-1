import logging
import unittest
import numpy
import scipy.sparse 
import sklearn.metrics 
from sandbox.util.MCEvaluator import MCEvaluator
from sandbox.util.SparseUtils import SparseUtils

class  MCEvaluatorTest(unittest.TestCase):
    def setUp(self): 
        numpy.random.seed(21)
    
    def testMeanSqError(self): 
        numExamples = 10
        testX = scipy.sparse.rand(numExamples, numExamples)
        testX = testX.tocsr()
        
        predX = testX.copy() 
        error = MCEvaluator.meanSqError(testX, predX)
        self.assertEquals(error, 0.0)
        
        testX = numpy.random.rand(numExamples, numExamples)
        predX = testX + numpy.random.rand(numExamples, numExamples)*0.5 
        
        error2 = ((testX-predX)**2).sum()/(numExamples**2)
        error = MCEvaluator.meanSqError(scipy.sparse.csr_matrix(testX), scipy.sparse.csr_matrix(predX)) 
        
        self.assertEquals(error, error2)
        
    def testPrecisionAtK(self): 
        m = 10 
        n = 5 
        r = 3 
        k = m*n
        
        X, U, s, V = SparseUtils.generateSparseLowRank((m,n), r, k, verbose=True)
        mean = X.data.mean()
        X.data[X.data <= mean] = 0
        X.data[X.data > mean] = 1
        
        import sppy 
        X = sppy.csarray(X)
        
        print(MCEvaluator.precisionAtK(X, U, V, 4))
        
            
    def testLocalAUC(self): 
        m = 10 
        n = 20 
        k = 2 
        numInds = 100
        X, U, s, V = SparseUtils.generateSparseLowRank((m, n), k, numInds, verbose=True)
        
        X = X/X
        Z = U.dot(V.T)

        
        localAuc = numpy.zeros(m)
        
        for i in range(m): 
            localAuc[i] = sklearn.metrics.roc_auc_score(numpy.ravel(X[i, :].todense()), Z[i, :])
                    
        localAuc = localAuc.mean()
        
        u = 1.0
        localAuc2 = MCEvaluator.localAUC(X, U, V, u)

        self.assertEquals(localAuc, localAuc2)
        
        #Now try a large r 
        u =0

        localAuc2 = MCEvaluator.localAUC(X, U, V, u)
        self.assertEquals(localAuc2, 0)
        
    def testLocalAucApprox(self): 
        m = 100 
        n = 200 
        k = 2 
        numInds = 100
        X, U, s, V = SparseUtils.generateSparseLowRank((m, n), k, numInds, verbose=True)
        
        X = X/X
        Z = U.dot(V.T)

        u = 1.0
        
        
        localAuc = MCEvaluator.localAUC(X, U, V, u)
        
        samples = numpy.arange(50, 200, 10)
        
        for i, sampleSize in enumerate(samples): 
            numAucSamples = sampleSize
            localAuc2 = MCEvaluator.localAUCApprox(X, U, V, u, numAucSamples)

            self.assertAlmostEqual(localAuc2, localAuc, 1)        
        
if __name__ == '__main__':
    unittest.main()

