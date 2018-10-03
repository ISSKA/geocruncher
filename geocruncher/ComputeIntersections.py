import sys
import numpy as np

class MapIntersections:
	
    def output(xCoord,yCoord,nPoints,model):  
		
        topography=model.topography
		
        def computeRank(a,b):
            evaluate_z = topography.evaluate_z
            ranks=model.rank
            return ranks([a,b,evaluate_z([a,b])])
	        				                    	        
        def findIntersectionY(rankUp,rankDown,y1,y2,x):
            if rankUp != rankDown:
                while (abs(y1-y2)>(abs(yCoord[0]-yCoord[1])/1000)):
                    yMid=(y1+y2)/2
                    if computeRank(x,y1)==computeRank(x,yMid):
                        y1=yMid
                    else:
                        y2=yMid
                return ((y1+y2)/2)
            else:
                return(-1)
                
        def findIntersectionX(rankLeft,rankRight,x1,x2,y):
            if rankLeft != rankRight:
                while (abs(x1-x2)>(abs(xCoord[0]-xCoord[1])/1000)):
                    xMid=(x1+x2)/2
                    if computeRank(x1,y)==computeRank(x2,y):
                        x1=xMid
                    else:
                        x2=xMid
                return ((x1+x2)/2)
            else:
                return(-1)                
                  
        def computeInterface(index):
            #Find the intersections between two interpolation points
            startIndex=index*nPoints+(nPoints-1)*index
            yBoundaryList[startIndex:startIndex+nPoints-1]=list(map(findIntersectionY,rankMatrix[index][1:nPoints],rankMatrix[index][0:nPoints-1],yMapRange[0:nPoints-1],yMapRange[1:nPoints],np.ones(nPoints)*xMapRange[index]))
            xBoundaryList[startIndex:startIndex+nPoints-1]= np.ones(nPoints-1)*xMapRange[index]
            ranksBelowList[startIndex:startIndex+nPoints-1]=rankMatrix[index][0:nPoints-1]

            xBoundaryList[startIndex+nPoints:startIndex+nPoints*2]=list(map(findIntersectionX,rankMatrix[:][index],rankMatrix[:][index+1],np.ones(nPoints)*xMapRange[index],np.ones(nPoints)*xMapRange[index+1],yMapRange))
            yBoundaryList[startIndex+nPoints:startIndex+nPoints*2]=yMapRange
            ranksBelowList[startIndex+nPoints:startIndex+nPoints*2]=list(map(computeRank,x[:][index]+xStep/2,y[:][index]-yStep))

        def computeRankMatrix(index):
            return np.array(list(map(computeRank,x[index],y[index]))).transpose()

        slope=(yCoord[0]-yCoord[1])/(xCoord[0]-xCoord[1])
        
        xStep=(xCoord[1]-xCoord[0])/nPoints
        yStep=(yCoord[1]-yCoord[0])/nPoints


        #x,y,z Coordinates expressed in real coordinates
        xMapRange=np.linspace(xCoord[0],xCoord[1],nPoints)
        yMapRange=np.linspace(yCoord[0],yCoord[1],nPoints)
        
        #x, z = np.ogrid[xCoord[0]:xCoord[1]:nPoints , zCoord[0]:zCoord[1]:nPoints]
        y, x = np.meshgrid(yMapRange, xMapRange)
		
        #x,y interpolation points
        ranksBelowList=np.zeros((nPoints)*(nPoints-1)*2)
        yBoundaryList=np.ones((nPoints)*(nPoints-1)*2)*(-1)
        xBoundaryList=np.ones((nPoints)*(nPoints-1)*2)*(-1)
                
        #Main computation loop
        rankMatrix=list(map(computeRankMatrix,(np.arange(0,nPoints))))
        
        list(map(computeInterface,(np.arange(0,nPoints-1))))
        
        
        xBoundaryList= xBoundaryList[yBoundaryList!=-1]
        ranksBelowList = ranksBelowList[yBoundaryList!=-1]
        yBoundaryList = yBoundaryList[yBoundaryList!=-1]         
     
        ranksBelowList = ranksBelowList[xBoundaryList!=-1]
        yBoundaryList = yBoundaryList[xBoundaryList!=-1]
        xBoundaryList= xBoundaryList[xBoundaryList!=-1]
        
        return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksBelowList.astype(int), precision=0, separator=',',suppress_small=True))

	
            	
class CrossSectionIntersections:

    def output(xCoord,yCoord,zCoord,nPoints,model,imgSize):
		
        def computeRank(x,z):
            y=slope*(x-xCoord[0])+yCoord[0] 
            ranks=model.rank
            return ranks([x,y,z])
			
        def findIntersectionY(rankUp,rankDown,z1,z2,x):
            if rankUp != rankDown:
                while (abs(z1-z2)>(abs(zCoord[0]-zCoord[1])/1000)):
                    zMid=(z1+z2)/2
                    if computeRank(x,z1)==computeRank(x,zMid):
                        z1=zMid
                    else:
                        z2=zMid
                return ((z1+z2)/2)
            else:
                return(-1)
                
        def findIntersectionX(rankLeft,rankRight,x1,x2,z):
            if rankLeft != rankRight:
                while (abs(x1-x2)>(abs(xCoord[0]-xCoord[1])/1000)):
                    xMid=(x1+x2)/2
                    if computeRank(x1,z)==computeRank(x2,z):
                        x1=xMid
                    else:
                        x2=xMid
                return ((x1+x2)/2)
            else:
                return(-1)                
                  
        def computeInterface(index):
            #Find the intersections between two interpolation points
            startIndex=index*nPoints+(nPoints-1)*index
            yBoundaryList[startIndex:startIndex+nPoints-1]=list(map(findIntersectionY,rankMatrix[index][1:nPoints],rankMatrix[index][0:nPoints-1],zCrossSectionRange[0:nPoints-1],zCrossSectionRange[1:nPoints],np.ones(nPoints)*xCrossSectionRange[index]))
            xBoundaryList[startIndex:startIndex+nPoints-1]= np.ones(nPoints-1)*xCrossSectionRange[index]
            ranksBelowList[startIndex:startIndex+nPoints-1]=rankMatrix[index][0:nPoints-1]

            xBoundaryList[startIndex+nPoints:startIndex+nPoints*2]=list(map(findIntersectionX,rankMatrix[:][index],rankMatrix[:][index+1],np.ones(nPoints)*xCrossSectionRange[index],np.ones(nPoints)*xCrossSectionRange[index+1],zCrossSectionRange))
            yBoundaryList[startIndex+nPoints:startIndex+nPoints*2]=zCrossSectionRange
            ranksBelowList[startIndex+nPoints:startIndex+nPoints*2]=list(map(computeRank,x[:][index]+xStep/2,z[:][index]-zStep))

        def computeRankMatrix(index):
            return np.array(list(map(computeRank,x[index],z[index]))).transpose()

        slope=(yCoord[0]-yCoord[1])/(xCoord[0]-xCoord[1])
        
        xStep=(xCoord[1]-xCoord[0])/nPoints
        zStep=(zCoord[1]-zCoord[0])/nPoints

        #x Coordinates expressed in pixels
        xImgRange=np.linspace(0,imgSize[1],nPoints) 
        zImgRange=np.linspace(0,imgSize[0],nPoints) 

        #x,y,z Coordinates expressed in real coordinates
        xCrossSectionRange=np.linspace(xCoord[0],xCoord[1],nPoints) 
        zCrossSectionRange=np.linspace(zCoord[0],zCoord[1],nPoints) 
        
        #x, z = np.ogrid[xCoord[0]:xCoord[1]:nPoints , zCoord[0]:zCoord[1]:nPoints]
        z, x = np.meshgrid(zCrossSectionRange, xCrossSectionRange)
		
        #x,y interpolation points
        ranksBelowList=np.zeros((nPoints)*(nPoints-1)*2)
        yBoundaryList=np.ones((nPoints)*(nPoints-1)*2)*(-1)
        xBoundaryList=np.ones((nPoints)*(nPoints-1)*2)*(-1)
                
        #Main computation loop
        rankMatrix=list(map(computeRankMatrix,(np.arange(0,nPoints))))
        
        list(map(computeInterface,(np.arange(0,nPoints-1))))
        
        
        xBoundaryList= xBoundaryList[yBoundaryList!=-1]
        ranksBelowList = ranksBelowList[yBoundaryList!=-1]
        yBoundaryList = yBoundaryList[yBoundaryList!=-1]         
     
        ranksBelowList = ranksBelowList[xBoundaryList!=-1]
        yBoundaryList = yBoundaryList[xBoundaryList!=-1]
        xBoundaryList= xBoundaryList[xBoundaryList!=-1]
        
        xBoundaryList=((xBoundaryList-(xCoord[0]))*(imgSize[1]))/((xCoord[1])-(xCoord[0])) #coord conversions
        yBoundaryList = imgSize[0]-((yBoundaryList-(zCoord[0]))*(imgSize[0])/((zCoord[1])-(zCoord[0])))  #coord conversions

        return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksBelowList.astype(int), precision=0, separator=',',suppress_small=True))
