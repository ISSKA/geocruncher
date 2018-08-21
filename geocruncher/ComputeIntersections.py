import sys
import numpy as np

class MapIntersections:
	
    def output(xCoord,yCoord,nPoints,model,topography):
            np.set_printoptions(suppress=True, threshold=7000)
            xMapRange=np.linspace(xCoord[0],xCoord[1],nPoints)
            yMapRange=np.linspace(yCoord[1],yCoord[0],nPoints)
            x0=xCoord[0]
            y0=yCoord[0]
            xBoundaryList=np.array([])
            yBoundaryList=np.array([])
            ranksBeforeList=np.array([])
            for i in range(0, nPoints):
                u=0
                x=xMapRange[i]
                for j in range(0, nPoints-1):
                    ranksBefore=model.rank([x,yMapRange[j],topography.evaluate_z([x,yMapRange[j]])])
                    ranksAfter=model.rank([x,yMapRange[j+1],topography.evaluate_z([x,yMapRange[j+1]])])
                    if ranksBefore!=ranksAfter:
                        yMid=MapIntersections.bijection(x,yMapRange[j],yMapRange[j+1],topography,abs(xCoord[0]-xCoord[1]),model)
                        yBoundary=yCoord[1]-yMid+yCoord[0]
                        xBoundary=xMapRange[i]
                        xBoundaryList=np.append(xBoundaryList, xBoundary)
                        yBoundaryList=np.append(yBoundaryList, round(yBoundary))
                        ranksBeforeList=np.append(ranksBeforeList,round(ranksBefore))

           
            return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksBeforeList.astype(int), precision=0, separator=',',suppress_small=True))
            
    def bijection(x,y1,y2,topography,imgSize,model):
        while (abs(y1-y2)>(imgSize/10000)):
            yMid=(y1+y2)/2
            if model.rank([x,y1,topography.evaluate_z([x,y1])])==model.rank([x,yMid,topography.evaluate_z([x,yMid])]):
                y1=yMid
            else:
                y2=yMid
        return yMid


            	
class CrossSectionIntersections:

    def output(xCoord,yCoord,zCoord,nPoints,model,imgSize):
            slope=(yCoord[0]-yCoord[1])/(xCoord[0]-xCoord[1])
            np.set_printoptions(suppress=True)
            np.set_printoptions(threshold=np.nan)
            xImgRange=np.linspace(imgSize[1],0,nPoints)
            yImgRange=np.linspace(0,imgSize[0],nPoints)
            nPointsZ=nPoints
            xCrossSectionRange=np.linspace(xCoord[1],xCoord[0],nPoints)
            zCrossSectionRange=np.linspace(zCoord[0],zCoord[1],nPointsZ)
            x0=xCoord[0]
            y0=yCoord[0]
            xBoundaryList=np.array([])
            yBoundaryList=np.array([])
            ranksBeforeList=np.array([])
            data=np.array([[0],[0],[0, 0, 0]])
            
            for i in range(0, nPoints):
                u=0
                x=xCrossSectionRange[i]
                y=slope*(xCrossSectionRange[i]-x0)+y0
                for j in range(0, nPointsZ-1):
                    ranksBefore=model.rank([x,y,zCrossSectionRange[j+1]])
                    ranksAfter=model.rank([x,y,zCrossSectionRange[j]])
                    if ranksBefore!=ranksAfter:
                        zMid=CrossSectionIntersections.bijection(x,y,zCrossSectionRange[j],zCrossSectionRange[j+1],imgSize,model)
                        yBoundary=imgSize[0]-((zMid-min(zCoord))*(imgSize[0])/(max(zCoord)-min(zCoord)))
                        xBoundary=xImgRange[i]
                        xBoundaryList=np.append(xBoundaryList, xBoundary)
                        yBoundaryList=np.append(yBoundaryList, yBoundary)
                        ranksBeforeList=np.append(ranksBeforeList,ranksBefore)                    
            return (np.array2string(xBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(yBoundaryList.astype(int), precision=0, separator=',',suppress_small=True),np.array2string(ranksBeforeList.astype(int), precision=0, separator=',',suppress_small=True))

            
    def bijection(x,y,z1,z2,imgSize,model):
        while (abs(z1-z2)>(imgSize[1]/10000)):
            zMid=(z1+z2)/2
            if model.rank([x,y,zMid])==model.rank([x,y,z1]):
                z1=zMid
            else:
                z2=zMid
        return zMid
        
