var figue = function () {
	function euclidianDistance (vec1 , vec2) {
		var N = vec1.length ;
		var d = 0 ;
		for (var i = 0 ; i < N ; i++)
			d += Math.pow (vec1[i] - vec2[i], 2)
		d = Math.sqrt (d) ;
		return d ;
	}

	function manhattanDistance (vec1 , vec2) {
		var N = vec1.length ;
		var d = 0 ;
		for (var i = 0 ; i < N ; i++)
			d += Math.abs (vec1[i] - vec2[i])
		return d ;
	}

	function maxDistance (vec1 , vec2) {
		var N = vec1.length ;
		var d = 0 ;
		for (var i = 0 ; i < N ; i++)
			d = Math.max (d , Math.abs (vec1[i] - vec2[i])) ;
		return d ;
	}

	function addVectors (vec1 , vec2) {
		var N = vec1.length ;
		var vec = new Array(N) ;
		for (var i = 0 ; i < N ; i++)
			vec[i] = vec1[i] + vec2[i] ;
		return vec ;
	}	

	function multiplyVectorByValue (value , vec) {
		var N = vec.length ;
		var v = new Array(N) ;
		for (var i = 0 ; i < N ; i++)
			v[i] = value * vec[i] ;
		return v ;
	}	
	
	function vectorDotProduct (vec1, vec2) {
		var N = vec1.length ;
		var s = 0 ;
		for (var i = 0 ; i < N ; i++)
			s += vec1[i] * vec2[i] ;
		return s ;
	}
	

	function repeatChar(c, n) {
		var str = "";
		for (var i = 0 ; i < n ; i++)
			str += c ;
		return str ;
	}
	
	function calculateCentroid (c1Size , c1Centroid , c2Size , c2Centroid) {
		var newCentroid = new Array(c1Centroid.length) ;
		var newSize = c1Size + c2Size ;
		for (var i = 0 ; i < c1Centroid.length ; i++) 
			newCentroid[i] = (c1Size * c1Centroid[i] + c2Size * c2Centroid[i]) / newSize ;
		return newCentroid ;	
	}


	function centerString(str, width) {
		var diff = width - str.length ;
		if (diff < 0)
			return ;

		var halfdiff = Math.floor(diff / 2) ;
		return repeatChar (" " , halfdiff) + str + repeatChar (" " , diff - halfdiff)  ;
	}

	function putString(str, width, index) {
		var diff = width - str.length ;
		if (diff < 0)
			return ;

		return repeatChar (" " , index) + str + repeatChar (" " , width - (str.length+index)) ;
	}

	function prettyVector(vector) {
		var vals = new Array(vector.length) ;
		var precision = Math.pow(10, figue.PRINT_VECTOR_VALUE_PRECISION) ; 
		for (var i = 0 ; i < vector.length ; i++)
			vals[i] = Math.round(vector[i]*precision)/precision ;
		return vals.join(",")
	}

	function prettyValue(value) {
		var precision = Math.pow(10, figue.PRINT_VECTOR_VALUE_PRECISION) ; 
		return String (Math.round(value*precision)/precision) ;
	}

	
	function getRandomVectors(k, vectors) {
		/*  Returns a array of k distinct vectors randomly selected from a the input array of vectors
			Returns null if k > n or if there are less than k distinct objects in vectors */
		
		var n = vectors.length ;
		if ( k > n ) 
			return null ;
		
		var selected_vectors = new Array(k) ;
		var selected_indices = new Array(k) ;
		
		var tested_indices = new Object ;
		var tested = 0 ;
		var selected = 0 ;
		var i , vector, select ;
		while (selected < k) {
			if (tested == n)
				return null ;
			
			var random_index = Math.floor(Math.random()*(n)) ;
			if (random_index in tested_indices)
				continue ;
			
			tested_indices[random_index] = 1;
			tested++ ;
			vector = vectors[random_index] ;
			select = true ;
			for (i = 0 ; i < selected ; i++) {
				if ( vector.compare (selected_vectors[i]) ) {
					select = false ;
					break ;
				}
			}
			if (select) {
				selected_vectors[selected] = vector ;
				selected_indices[selected] = random_index ; 
				selected++ ;
			}
		}
		return {'vectors': selected_vectors, 'indices': selected_indices} ;
	}
	
	function kmeans (k, vectors) {
		var n = vectors.length ;
		var assignments = new Array(n) ;
		var clusterSizes = new Array(k) ;
		var repeat = true ;
		var nb_iters = 0 ;
		var centroids = null ;
		
		var t = getRandomVectors(k, vectors) ;
		if (t == null)
			return null ;
		else
			centroids = t.vectors ;
			
		while (repeat) {

			// assignment step
			for (var j = 0 ; j < k ; j++)
				clusterSizes[j] = 0 ;
			
			for (var i = 0 ; i < n ; i++) {
				var vector = vectors[i] ;
				var mindist = Number.MAX_VALUE ;
				var best ;
				for (var j = 0 ; j < k ; j++) {
					var dist = euclidianDistance (centroids[j], vector)
					if (dist < mindist) {
						mindist = dist ;
						best = j ;
					}
				}
				clusterSizes[best]++ ;
				assignments[i] = best ;
			}
		
			// update centroids step
			var newCentroids = new Array(k) ;
			for (var j = 0 ; j < k ; j++)
				newCentroids[j] = null ;

			for (var i = 0 ; i < n ; i++) {
				var cluster = assignments[i] ;
				if (newCentroids[cluster] == null)
					newCentroids[cluster] = vectors[i] ;
				else
					newCentroids[cluster] = addVectors (newCentroids[cluster] , vectors[i]) ;	
			}

			for (var j = 0 ; j < k ; j++) {
				newCentroids[j] = multiplyVectorByValue (1/clusterSizes[j] , newCentroids[j]) ;
			}	
			
			// check convergence
			repeat = false ;
			for (var j = 0 ; j < k ; j++) {
				if (! newCentroids[j].compare (centroids[j])) {
					repeat = true ; 
					break ; 
				}
			}
			centroids = newCentroids ;
			nb_iters++ ;
			
			// check nb of iters
			if (nb_iters > figue.KMEANS_MAX_ITERATIONS)
				repeat = false ;
			
		}
		return { 'centroids': centroids , 'assignments': assignments} ;

	}
			
	function Matrix (rows,cols) 
	{
		this.rows = rows ;
		this.cols = cols ;
		this.mtx = new Array(rows) ; 

		for (var i = 0 ; i < rows ; i++)
		{
			var row = new Array(cols) ;
			for (var j = 0 ; j < cols ; j++)
				row[j] = 0;
			this.mtx[i] = row ;
		}
	}

	function Node (label,left,right,dist, centroid) 
	{
		this.label = label ;
		this.left = left ;
		this.right = right ;
		this.dist = dist ;
		this.centroid = centroid ;
		if (left == null && right == null) {
			this.size = 1 ;
			this.depth = 0 ;
		} else {
			this.size = left.size + right.size ;
			this.depth = 1 + Math.max (left.depth , right.depth ) ;
		}
	}



	return { 
		SINGLE_LINKAGE: 0,
		COMPLETE_LINKAGE: 1,
		AVERAGE_LINKAGE:2 ,
		EUCLIDIAN_DISTANCE: 0,
		MANHATTAN_DISTANCE: 1,
		MAX_DISTANCE: 2,
		PRINT_VECTOR_VALUE_PRECISION: 2,
		KMEANS_MAX_ITERATIONS: 10,
		FCMEANS_MAX_ITERATIONS: 3,

		Matrix: Matrix,
		Node: Node,
		kmeans: kmeans,
	}
}() ;


figue.Matrix.prototype.toString = function() 
{
	var lines = [] ;
	for (var i = 0 ; i < this.rows ; i++) 
		lines.push (this.mtx[i].join("\t")) ;
	return lines.join ("\n") ;
}


figue.Matrix.prototype.copy = function() 
{
	var duplicate = new figue.Matrix(this.rows, this.cols) ;
	for (var i = 0 ; i < this.rows ; i++)
		duplicate.mtx[i] = this.mtx[i].slice(0); 
	return duplicate ;
}

figue.Node.prototype.isLeaf = function() 
{
	if ((this.left == null) && (this.right == null))
		return true ;
	else
		return false ;
}

figue.Node.prototype.buildDendogram = function (sep, balanced,withLabel,withCentroid, withDistance)
{
	lines = figue.generateDendogram(this, sep, balanced,withLabel,withCentroid, withDistance) ;
	return lines.join ("\n") ;	
}


Array.prototype.compare = function(testArr) {
    if (this.length != testArr.length) return false;
    for (var i = 0; i < testArr.length; i++) {
        if (this[i].compare) { 
            if (!this[i].compare(testArr[i])) return false;
        }
        if (this[i] !== testArr[i]) return false;
    }
    return true;
}