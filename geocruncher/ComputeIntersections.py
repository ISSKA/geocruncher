import sys
import numpy as np

class MapIntersections:
	
    def output(xCoord,yCoord,nPoints,model,topography):  
		
        def computeRank(a,b):
            evaluate_z = topography.evaluate_z
            ranks=model.rank
            return ranks([a,b,evaluate_z([a,b])])
	        				
        def findIntersection(rankDown,rankUp,x,y1,y2):
            if rankUp != rankDown:
                while (abs(y1-y2)>(abs(xCoord[0]-xCoord[1])/500)):
                    yMid=(y1+y2)/2
                    if computeRank(x,y1)==computeRank(x,yMid):
                        y1=yMid
                    else:
                        y2=yMid
                # transformation between real coordinates and image coordinates
                return(yMid)
            else:
                return(-1)
                
        def computeColumn(index):
			#Compute the ranks of each interpolation points
            rankVector = list(map(computeRank,xInterp[index][:],yInterp[index][:]))
            ranksBelowList[index]=rankVector[1:nPoints*zInterpFactor]
            #Find the intersections between two interpolation points    
            yInterp[index][0:nPoints*zInterpFactor-1]=list(map(findIntersection,rankVector[1:nPoints*zInterpFactor],rankVector[0:nPoints*zInterpFactor-1],xInterp[index][1:nPoints*zInterpFactor],yInterp[index][1:nPoints*zInterpFactor],yInterp[index][0:nPoints*zInterpFactor-1]))

     
        #factor between number of interpolation in x and z
        zInterpFactor=2
                
        #x,y,z Coordinates expressed in real coordinates
        xMapRange=np.linspace(xCoord[0],xCoord[1],nPoints)
        yMapRange=np.linspace(yCoord[0],yCoord[1],nPoints*zInterpFactor)
        
        #x,y interpolation points + list of ranks
        xInterp= np.repeat([xMapRange], [nPoints*zInterpFactor], axis=0).transpose()
        yInterp= np.repeat([yMapRange.transpose()], [nPoints], axis=0)
        ranksBelowList=np.full((nPoints,nPoints*zInterpFactor-1),-1)
        
        #Main computation loop
        list(map(computeColumn,np.arange(0,nPoints)))
        
        #Output data treatment
        yInterp= np.delete(yInterp, nPoints*zInterpFactor-1, 1)
        xInterp= np.delete(xInterp, nPoints*zInterpFactor-1, 1)

        xBoundaryList= xInterp[yInterp!=-1]
        ranksBelowList = ranksBelowList[yInterp!=-1]
        yBoundaryList = yInterp[yInterp!=-1]
        	        
        return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksBelowList.astype(int), precision=0, separator=',',suppress_small=True))

	
	
            	
class CrossSectionIntersections:

    def output(xCoord,yCoord,zCoord,nPoints,model,imgSize):
		
        def computeRank(a,b,c):
            ranks=model.rank
            return ranks([a,b,c])
			
        def findIntersection(rankUp,rankDown,z1,z2,x,y):
            if rankUp != rankDown:
                while (abs(z1-z2)>(imgSize[1]/1000)):
                    zMid=(z1+z2)/2
                    if computeRank(x,y,zMid)==computeRank(x,y,z1):
                        z1=zMid
                    else:
                        z2=zMid
                # transformation between real coordinates and image coordinates
                return(imgSize[0]-((zMid-(zCoord[0]))*(imgSize[0])/((zCoord[1])-(zCoord[0]))))
            else:
                return(-1)
                
                  
        def computeColumn(index):
			#Compute the ranks of each interpolation points
            rankVector = list(map(computeRank,xInterp[:][index],yInterp[:][index],zCrossSectionRange))
            ranksBelowList[index]=rankVector[0:nPoints*zInterpFactor-1]
            #Find the intersections between two interpolation points
            yBoundaryList[index][0:nPoints*zInterpFactor-1]=list(map(findIntersection,rankVector[1:nPoints*zInterpFactor],rankVector[0:nPoints*zInterpFactor-1],zCrossSectionRange[0:nPoints*zInterpFactor-1],zCrossSectionRange[1:nPoints*zInterpFactor],xInterp[index],yInterp[index]))
	        
        slope=(yCoord[0]-yCoord[1])/(xCoord[0]-xCoord[1])
        
        #factor between number of interpolation in x and z
        zInterpFactor=3 
        
        #x Coordinates expressed in pixels
        xImgRange=np.linspace(0,imgSize[1],nPoints) 
        
        #x,y,z Coordinates expressed in real coordinates
        xCrossSectionRange=np.linspace(xCoord[0],xCoord[1],nPoints) 
        yCrossSectionRange=slope*(xCrossSectionRange-xCoord[0])+yCoord[0] 
        zCrossSectionRange=np.linspace(zCoord[0],zCoord[1],nPoints*zInterpFactor) 
        
        #x,y interpolation points
        xInterp= np.repeat([xCrossSectionRange], [nPoints*zInterpFactor], axis=0).transpose()
        yInterp= np.repeat([yCrossSectionRange], [nPoints*zInterpFactor], axis=0).transpose()
        ranksBelowList=np.full((nPoints,nPoints*zInterpFactor-1),-1)
        yBoundaryList=np.full((nPoints,nPoints*zInterpFactor-1),-1)

        #Main computation loop
        list(map(computeColumn,(np.arange(0,nPoints))))
          
        #Output data treatment
        xBoundaryList= np.repeat([xImgRange], [nPoints*zInterpFactor], axis=0).transpose()
        xBoundaryList= np.delete(xBoundaryList, nPoints*zInterpFactor-1, 1)

        xBoundaryList= xBoundaryList[yBoundaryList!=-1]
        ranksAfterList = ranksBelowList[yBoundaryList!=-1]
        yBoundaryList = yBoundaryList[yBoundaryList!=-1]
        
        return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksAfterList.astype(int), precision=0, separator=',',suppress_small=True))
