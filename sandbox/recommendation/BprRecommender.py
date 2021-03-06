"""
Wrapper to use gamboviol implementation of BPR.
"""

import numpy 
import logging
import multiprocessing
from sandbox.util.MCEvaluator import MCEvaluator 
from sandbox.util.Sampling import Sampling
from bprCython import AllUserUniformItem, BPRArgs, BPR 
from sandbox.recommendation.RecommenderUtils import computeTestMRR, computeTestF1
from sandbox.recommendation.AbstractRecommender import AbstractRecommender

class BprRecommender(AbstractRecommender): 
    """
    An interface to the BPR recommender system. 
    """
    
    def __init__(self, k, lmbdaUser=0.1, lmbdaPos=0.1, lmbdaNeg=0.1, gamma=0.1, numProcesses=None): 
        """
        k is the number of factors, lambda is the regularistion and gamma is the learning rate 
        """
        super(BprRecommender, self).__init__(numProcesses)
        self.k = k 
        self.lmbdaUser = lmbdaUser
        self.lmbdaPos = lmbdaPos
        self.lmbdaNeg = lmbdaNeg
        self.gamma = gamma
                
        self.maxIterations = 25
        self.numAucSamples = 5
        self.recordStep = 5
        
        #Model selection parameters 
        self.ks = 2**numpy.arange(3, 8)
        self.lmbdaUsers = 2.0**-numpy.arange(1, 20, 4)
        #self.lmbdaPoses = 2.0**-numpy.arange(1, 20, 4)
        #self.lmbdaNegs = 2.0**-numpy.arange(1, 20, 4)
        self.lmbdaItems = 2.0**-numpy.arange(1, 20, 4)
        self.gammas = 2.0**-numpy.arange(1, 20, 4)
        
    def learnModel(self, X, U=None, V=None):
        args = BPRArgs()
        args.learning_rate = self.gamma
        args.user_regularization = self.lmbdaUser
        args.negative_item_regularization = self.lmbdaPos 
        args.positive_item_regularization = self.lmbdaNeg
        
        model = BPR(self.k, args)
        model.numAucSamples = self.numAucSamples
        model.recordStep = self.recordStep 
    
        sampler = AllUserUniformItem()
        user_factors, item_factors = model.train(X, sampler, self.maxIterations)
        
        self.U = user_factors
        self.V = item_factors
    
    def predict(self, maxItems): 
        return MCEvaluator.recommendAtk(self.U, self.V, maxItems)
        
    def modelSelect(self, X, colProbs=None): 
        """
        Perform model selection on X and return the best parameters. 
        """
        m, n = X.shape
        trainTestXs = Sampling.shuffleSplitRows(X, self.folds, self.validationSize, csarray=True, colProbs=colProbs)
        testMetrics = numpy.zeros((self.ks.shape[0], self.lmbdaUsers.shape[0], self.lmbdaItems.shape[0], self.gammas.shape[0], len(trainTestXs)))
        
        logging.debug("Performing model selection with test leave out per row of " + str(self.validationSize))
        paramList = []        
        
        for i, k in enumerate(self.ks): 
            for j, lmbdaUser in enumerate(self.lmbdaUsers): 
                for s, lmbdaItem in enumerate(self.lmbdaItems): 
                    for t, gamma in enumerate(self.gammas):
                        for icv, (trainX, testX) in enumerate(trainTestXs):
                            learner = self.copy()
                            learner.k = k  
                            learner.lmbdaUser = lmbdaUser 
                            learner.lmbdaPos = lmbdaItem
                            learner.lmbdaNeg = lmbdaItem
                            learner.gamma = gamma
                        
                            paramList.append((trainX, testX, learner))
            
        if self.numProcesses != 1: 
            pool = multiprocessing.Pool(processes=self.numProcesses, maxtasksperchild=100)
            resultsIterator = pool.imap(computeTestF1, paramList, self.chunkSize)
        else: 
            import itertools
            resultsIterator = itertools.imap(computeTestF1, paramList)
        
        for i, k in enumerate(self.ks): 
            for j, lmbdaUser in enumerate(self.lmbdaUsers): 
                for s, lmbdaPos in enumerate(self.lmbdaItems): 
                    for t, gamma in enumerate(self.gammas):
                        for icv, (trainX, testX) in enumerate(trainTestXs):        
                            testMetrics[i, j, s, t, icv] = resultsIterator.next()
                
        if self.numProcesses != 1: 
            pool.terminate()
        
        meanTestMetrics = numpy.mean(testMetrics, 4)
        stdTestMetrics = numpy.std(testMetrics, 4)
        
        logging.debug("ks=" + str(self.ks)) 
        logging.debug("lmbdaUsers=" + str(self.lmbdaUsers)) 
        logging.debug("lmbdaItems=" + str(self.lmbdaItems)) 
        logging.debug("gammas=" + str(self.gammas)) 
        logging.debug("Mean metrics=" + str(meanTestMetrics))
        
        
        indK, indLmdabUser, indLmbdaItem, indGamma = numpy.unravel_index(meanTestMetrics.argmax(), meanTestMetrics.shape)
        self.k = self.ks[indK]
        self.lmbdaUser = self.lmbdaUsers[indLmdabUser]
        self.lmbdaPos = self.lmbdaItems[indLmbdaItem]
        self.lmbdaNeg = self.lmbdaItems[indLmbdaItem]
        self.gamma = self.gammas[indGamma]

        logging.debug("Model parameters: " + str(self))
         
        return meanTestMetrics, stdTestMetrics
        
    def copy(self): 
        learner = BprRecommender(self.k, self.lmbdaUser, self.lmbdaPos, self.lmbdaNeg, self.gamma)
        self.copyParams(learner)
        learner.maxIterations = self.maxIterations 
        learner.numAucSamples = self.numAucSamples
        learner.recordStep = self.recordStep
        
        return learner 

    def __str__(self): 
        outputStr = "BPR Recommender: k=" + str(self.k) 
        outputStr += " lmbdaUser=" + str(self.lmbdaUser)
        outputStr += " lmbdaPos=" + str(self.lmbdaPos)
        outputStr += " lmbdaNeg=" + str(self.lmbdaNeg)
        outputStr += " gamma=" + str(self.gamma)
        outputStr += " maxIterations=" + str(self.maxIterations)
        outputStr += " numAucSamples=" + str(self.numAucSamples)
        outputStr += " recordStep=" + str(self.recordStep)
        outputStr += super(BprRecommender, self).__str__()
        
        return outputStr   
        

    def modelParamsStr(self): 
        outputStr = " k=" + str(self.k) + " lmbdaUser=" + str(self.lmbdaUser) + " lmbdaPos=" + str(self.lmbdaPos) +  " gamma=" + str(self.gamma)
        return outputStr 
