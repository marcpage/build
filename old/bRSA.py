#!/usr/bin/env python

__all__ = [ # exported symbols from this module
	"Key", # RSA Key
]

""" Based on rsa.py from Sybren Stuvel, Marloes de Boer and Ivo Tamboer, 2009-01-22

Gnu Public Licence (GPL) as well as the European Union Public Licence (EUPL)

source: http://stuvel.eu/rsa

"""
import os
import math
import types
import random

def bytes2int(bytes):
    """Converts a list of bytes or a string to an integer

    >>> (128*256 + 64)*256 + + 15
    8405007
    >>> l = [128, 64, 15]
    >>> bytes2int(l)
    8405007
    """
    if not (type(bytes) is types.ListType or type(bytes) is types.StringType):
        raise TypeError("You must pass a string or a list")
    # Convert byte stream to integer
    integer = 0
    for byte in bytes:
        integer *= 256
        if type(byte) is types.StringType:
        	byte = ord(byte)
        integer += byte
    return integer

def read_random_int(nbits):
    """Reads a random integer of approximately nbits bits rounded up
    to whole bytes"""
    nbytes = int(math.ceil(nbits/8))
    randomdata = os.urandom(nbytes)
    return bytes2int(randomdata)

def randint(minvalue, maxvalue):
    """Returns a random integer x with minvalue <= x <= maxvalue"""
    # Safety - get a lot of random data even if the range is fairly
    # small
    min_nbits = 32
    # The range of the random numbers we need to generate
    range = maxvalue - minvalue
    # Which is this number of bytes
    rangebytes = int(math.ceil(math.log(range, 2) / 8))
    # Convert to bits, but make sure it's always at least min_nbits*2
    rangebits = max(rangebytes * 8, min_nbits * 2)
    # Take a random number of bits between min_nbits and rangebits
    nbits = random.randint(min_nbits, rangebits)
    return (read_random_int(nbits) % range) + minvalue

def jacobi(a, b):
    """Calculates the value of the Jacobi symbol (a/b)
    """
    if a % b == 0:
        return 0
    result = 1
    while a > 1:
        if a & 1:
            if ((a-1)*(b-1) >> 2) & 1:
                result = -result
            b, a = a, b % a
        else:
            if ((b ** 2 - 1) >> 3) & 1:
                result = -result
            a = a >> 1
    return result

def fast_exponentiation(a, p, n):
    """Calculates r = a^p mod n
    """
    result = a % n
    remainders = []
    while p != 1:
        remainders.append(p & 1)
        p = p >> 1
    while remainders:
        rem = remainders.pop()
        result = ((a ** rem) * result ** 2) % n
    return result

def jacobi_witness(x, n):
    """Returns False if n is an Euler pseudo-prime with base x, and
    True otherwise.
    """
    j = jacobi(x, n) % n
    f = fast_exponentiation(x, (n-1)/2, n)
    if j == f:
    	return False
    return True

def randomized_primality_testing(n, k):
    """Calculates whether n is composite (which is always correct) or
    prime (which is incorrect with error probability 2**-k)

    Returns False if the number if composite, and True if it's
    probably prime.
    """
    q = 0.5     # Property of the jacobi_witness function
    t = int(math.ceil(k / math.log(1/q, 2)))
    for i in range(t+1):
        x = randint(1, n-1)
        if jacobi_witness(x, n):
        	return False
    return True

def is_prime(number):
    """Returns True if the number is prime, and False otherwise.

    >>> is_prime(42)
    0
    >>> is_prime(41)
    1
    """
    if randomized_primality_testing(number, 5):
        # Prime, according to Jacobi
        return True
    # Not prime
    return False

def getprime(nbits):
    """Returns a prime number of max. 'math.ceil(nbits/8)*8' bits. In
    other words: nbits is rounded up to whole bytes.

    >>> p = getprime(8)
    >>> is_prime(p-1)
    0
    >>> is_prime(p)
    1
    >>> is_prime(p+1)
    0
    """
    nbytes = int(math.ceil(nbits/8))
    while True:
        integer = read_random_int(nbits)
        integer |= 1 # Make sure it's odd
        if is_prime(integer): # Test for primeness
        	break
    return integer

def gcd(p, q):
    """Returns the greatest common divisor of p and q

    >>> gcd(42, 6)
    6
    """
    if abs(p)<abs(q):
    	return gcd(q, p)
    if q == 0:
    	return abs(p)
    return gcd(q, abs(p%q))

def are_relatively_prime(a, b):
    """Returns True if a and b are relatively prime, and False if they
    are not.

    >>> are_relatively_prime(2, 3)
    1
    >>> are_relatively_prime(2, 4)
    0
    """
    d = gcd(a, b)
    return (d == 1)

def extended_euclid_gcd(a, b):
    """Returns a tuple (d, i, j) such that d = gcd(a, b) = ia + jb
    """
    if b == 0:
        return (a, 1, 0)
    q = abs(a % b)
    r = long(a / b)
    (d, k, l) = extended_euclid_gcd(b, q)
    return (d, l, k - l*r)

def calculate_keys(p, q, nbits):
    """Calculates an encryption and a decryption key for p and q, and
    returns them as a tuple (e, d)"""
    n = p * q
    phi_n = (p-1) * (q-1)
    while True:
        # Make sure e has enough bits so we ensure "wrapping" through
        # modulo n
        e = getprime(max(8, nbits/2))
        if are_relatively_prime(e, n) and are_relatively_prime(e, phi_n):
        	break
    (d, i, j) = extended_euclid_gcd(e, phi_n)
    if not d == 1:
        raise Exception("e (%d) and phi_n (%d) are not relatively prime" % (e, phi_n))
    if not (e * i) % phi_n == 1:
        raise Exception("e (%d) and i (%d) are not mult. inv. modulo phi_n (%d)" % (e, i, phi_n))
    return (e, i)

def find_p_q(nbits):
    """Returns a tuple of two different primes of nbits bits"""
    p = getprime(nbits)
    while True:
        q = getprime(nbits)
        if not q == p:
        	break
    return (p, q)

kZeroBase= ord('0')
kAlphaBase= ord('a')
def int_to_radix(number, radix):
	if None == number:
		return ""
	if 2 > radix or radix > 36:
		raise ValueError("radix must be >= 2 and <= 36: "+str(radix))
	result= []
	negative= number < 0
	if negative:
		number*= -1
	while number != 0:
		remainder= number % radix
		if remainder <= 9:
			digit= chr(remainder + kZeroBase)
		else:
			digit= chr(remainder - 10 + kAlphaBase)
		result.append(digit)
		number/= radix
	if negative:
		result.append("-")
	result.reverse()
	return "".join(result)

class Key:
	kValidKeyStringCounts= [2,3,4]
	def __init__(self, param1= 512, param2= None):
		self.__init_fields()
		p1int= isinstance(param1, int) or isinstance(param1, long)
		p2int= isinstance(param2, int) or isinstance(param2, long)
		p1key= isinstance(param1, Key)
		p2key= isinstance(param2, Key)
		p1str= isinstance(param1, basestring)
		p1tuple= isinstance(param1, tuple)
		if p1key and None == param2:
			self.__merge_keys(self, param1)
		elif p1tuple and None == param2 and len(param1) == 3: # public-only key
			self.__d= param1[0]
			self.__p= param1[1]
			self.__q= param1[2]
		elif p1str and None == param2: # key string
			parts= param1.split(':')
			if not len(parts) in self.kValidKeyStringCounts:
				raise ValueError("Invalid Key String")
			if len(parts) == 2:
				self.__n= long(parts[0], 36)
			else:
				self.__d= long(parts[0], 36)
				self.__p= long(parts[1], 36)
				self.__q= long(parts[2], 36)
			if len(parts) == 2 or len(parts) == 4:
				self.__e= long(parts[-1], 36)
		elif p1key and p2key: # merging keys (public/private)
			self.__merge_keys(param1, param2)
		elif p1int and p2int: # public key
			self.__e= param1
			self.__n= param2
		elif p1int: # generate keypair
			self.__genkeys(param1)
		else:
			raise ValueError("Invalid Parameters: "+str( (param1, param2) ))
	def __repr__(self):
		return "Key('"+str(self)+"')"
	def __str__(self):
		keys= {
			'p': int_to_radix(self.__p, 36),
			'q': int_to_radix(self.__q, 36),
			'e': int_to_radix(self.__e, 36),
			'd': int_to_radix(self.__d, 36),
			'n': int_to_radix(self.__n, 36),
		}
		if self.isPrivate():
			if None != self.__e:
				return "%(d)s:%(p)s:%(q)s:%(e)s"%keys
			else:
				return "%(d)s:%(p)s:%(q)s"%keys
		else:
			return "%(n)s:%(e)s"%keys
	def equals(self, other, atLeastCompatible= False):
		if self.isPrivate() and other.isPrivate() and self.__e == other.__e:
			d= self.__d == other.__d
			q= self.__q == other.__q
			p= self.__p == other.__p
			return d and q and p
		if not self.isPrivate() and not other.isPrivate():
			e= self.__e == other.__e
			n= self.__n == other.__n
			return e and n
		if atLeastCompatible:
			return self.isPair(other)
		return False
	def isPair(self, other= None):
		if None == other:
			return self.isPrivate() and None != self.__e
		if not self.isPrivate() and not other.isPrivate():
			return False # Neither is a private key, cannot be paired
		if self.isPrivate() and other.isPrivate():
			myPublic= self.public()
			otherPublic= other.public()
			if None == myPublic and None == otherPublic:
				return False # Neither has a public key, cannot be paired
			if None == otherPublic:
				return other.isPair(self) # private.isPair(public)
		elif other.isPrivate():
			return other.isPair(self) # private.isPair(public)
		if None == other.__n:
			other.__n= other.__p * other.__q
		if other.__n != self.__ensure_n():
			return False
		phi_n= (self.__p - 1) * (self.__q - 1)
		return (other.__e * self.__d) % phi_n == 1
	def public(self):
		hasAnyPrivateParts= None != self.__p or None != self.__q or None != self.__d
		hasPublicParts= None != self.__e
		if hasPublicParts and not hasAnyPrivateParts:
			return self
		if self.isPrivate() and hasPublicParts:
			return Key(self.__e, self.__ensure_n())
		return None
	def private(self):
		if self.isPrivate() and None == self.__e:
			return self
		if None != self.__e:
			return Key( (self.__d, self.__p, self.__q) )
	def isPrivate(self):
		return None != self.__p and None != self.__q and None != self.__d
	def encrypt(self, data):
		if None == self.__e:
			raise ValueError("Must Encrypt with Public Key")
		dataChunkSize= self.__chunkSize()
		encryptedChunkSize= dataChunkSize + 1
		result= [int_to_radix(len(data), 36)+":"+int_to_radix(encryptedChunkSize, 36)+":"]
		while len(data) > 0:
			chunk= data[:dataChunkSize]
			if len(chunk) < dataChunkSize: # pad last chunk to full chunk size
				chunk+= "".join(["\0"]*(dataChunkSize - len(chunk)))
			chunkNumber= self.__str_to_long(chunk)
			encrypted= self.__encrypt(chunkNumber)
			result.append(self.__long_to_str(encrypted, encryptedChunkSize))
			if len(result[-1]) != encryptedChunkSize:
				raise AssertionError("Asked for a chunk of size %d but got %d"%(encryptedChunkSize, len(result[-1])))
			data= data[dataChunkSize:]
		return "".join(result)
	def decrypt(self, encrypted):
		if None == self.__d:
			raise ValueError("Must Decrypt with Private Key")
		result= []
		parts= encrypted.split(':', 2)
		finalDataSize= int(parts[0], 36)
		encryptedChunkSize= int(parts[1], 36)
		dataChunkSize= encryptedChunkSize - 1
		if len(parts[2])%encryptedChunkSize != 0:
			raise ValueError("Corrupted data stream")
		maxDataSize= dataChunkSize * len(parts[2])/encryptedChunkSize
		if maxDataSize - dataChunkSize > finalDataSize or finalDataSize > maxDataSize:
			raise ValueError("Corrupted data stream")
		payload= parts[2]
		while len(payload) > 0:
			chunk= payload[:encryptedChunkSize]
			encrypted= self.__str_to_long(chunk)
			decrypted= self.__decrypt(encrypted)
			if None == decrypted:
				return None # Not the correct key for this data
			result.append(self.__long_to_str(decrypted, dataChunkSize))
			payload= payload[encryptedChunkSize:]
		return "".join(result)[:finalDataSize]
	def sign(self, integer):
		result= self.__decrypt(integer)
		if None == result:
			if integer >= self.__ensure_n():
				integerBits= math.floor(math.log(integer, 2))
				nBits= math.floor(math.log(self.__ensure_n(), 2))
				if integerBits > nBits:
					raise OverflowError("Integer has too many bits %d, should be less than %d bits"%(integerBits, nBits))
				raise OverflowError("Integer is too big (bits= %d), make it less than %d bits"%(integerBits, nBits))
		return result
	def validate(self, integer, expected):
		if expected > 0:
			if expected > self.__n:
				return False
		if integer > 0:
			if integer > self.__n:
				return False
		return self.__encrypt(integer) == expected
	def __decrypt(self, integer):
		if integer > 0:
			if integer >= self.__ensure_n():
				return None
		return fast_exponentiation(integer, self.__d, self.__n)
	def __encrypt(self, integer):
		if integer > 0:
			if integer > self.__ensure_n():
				raise ValueError("Corrupted data stream")
		return fast_exponentiation(integer, self.__e, self.__ensure_n())
	def __str_to_long(self, value):
		result= long(0)
		byteSize= long(256)
		for character in value: # big endian
			result*= byteSize
			result+= ord(character)
		return result
	def __long_to_str(self, value, size= -1):
		bytes= []
		byteSize= long(256)
		while value > 0:
			bytes.append(chr(value%byteSize))
			value/= byteSize
		if size > 0 and len(bytes) < size:
			bytes.extend( ["\0"]*(size - len(bytes)) )
		bytes.reverse() # make it big endian
		return "".join(bytes)
	def __ensure_n(self):
		if None == self.__n:
			self.__n= self.__p * self.__q
		return self.__n
	def __merge_values(self, original, value, name):
		if None == original:
			return value
		if original != value and None != value:
			raise ValueError(
				name+" mismatch values in merge "
				+int_to_radix(original, 36)+","+int_to_radix(value, 36)
			)
		return original
	def __merge_keys(self, k1, k2):
		self.__e= self.__merge_values(self.__e, k1.__e, 'e')
		self.__n= self.__merge_values(self.__n, k1.__n, 'n')
		self.__d= self.__merge_values(self.__d, k1.__d, 'd')
		self.__p= self.__merge_values(self.__p, k1.__p, 'p')
		self.__q= self.__merge_values(self.__q, k1.__q, 'q')
		self.__e= self.__merge_values(self.__e, k2.__e, 'e')
		self.__n= self.__merge_values(self.__n, k2.__n, 'n')
		self.__d= self.__merge_values(self.__d, k2.__d, 'd')
		self.__p= self.__merge_values(self.__p, k2.__p, 'p')
		self.__q= self.__merge_values(self.__q, k2.__q, 'q')
		if None != self.__n and None != self.__p and None != self.__q:
			if self.__p * self.__q != self.__n:
				raise ValueError("Keys not compatible: "+str(k1)+" <-> "+str(k2))
		phi_n= (self.__p - 1) * (self.__q - 1)
		if None != self.__e and None != self.__d:
			if (self.__e * self.__d) % phi_n != 1:
				raise ValueError("Keys not compatible: "+str(k1)+" <-> "+str(k2))
	def __init_fields(self):
		self.__e= None
		self.__n= None
		self.__d= None
		self.__p= None
		self.__q= None
	def __chunkSize(self):
		""" Chunks are how many bytes each chunk can be
		"""
		nBits= math.floor(math.log(self.__ensure_n(), 2))
		return int((nBits - 1) / 8)
	def __genkeys(self, nbits):
		"""Generate RSA keys of nbits bits. Returns (p, q, e, d).
		Note: this can take a long time, depending on the key size.
		"""
		if nbits < 0:
			numberOfBitsToEncrypt= int(-0.5 * nbits)
		else:
			numberOfBitsToEncrypt= nbits
		numberOfBitsToGenerate= numberOfBitsToEncrypt + 9 # 64 -> 8
		# For some reason, d is sometimes negative. We don't know how
		# to fix it (yet), so we keep trying until everything is good
		self.__d= -1
		while self.__d < 0:
			self.__n= None
			(self.__p, self.__q) = find_p_q(numberOfBitsToGenerate)
			(self.__e, self.__d) = calculate_keys(self.__p, self.__q, numberOfBitsToGenerate)
			actualNBits= math.floor(math.log(self.__ensure_n(), 2) / 2.0)
			if self.__d > 0:
				pass
			if actualNBits <= numberOfBitsToEncrypt:
				self.__d= -1

if __name__ == "__main__":
	import md5
	k1= Key(-512) # large enough to encrypt sha512
	pu1= k1.public()
	pr1= k1.private()
	k1p= Key(pr1, pu1)
	k1o= Key(k1, pu1)
	k2= Key(-512) # large enough to encrypt sha512
	pu2= k2.public()
	pr2= k2.private()
	k2p= Key(pr2, pu2)
	k2o= Key(k2, pu2)
	integer= long(md5.new("Testing").hexdigest(), 16) # text to sign
	if not k1.validate(k1.sign(integer), integer):
		raise AssertionError("k1 did not sign correctly")
	contents= open(__file__, 'r').read()
	values= str( ( ("f:",k1, "pu:",pu1, "pr:",pr1) , ("f:",k2, "pu:",pu2, "pr:",pr2) ) )
	encryptTests= (
		(k1, k1, True), (k1, pr1, True), (k1, k1p, True), (k1, k1o, True), (pu1, k1, True), (pu1, pr1, True), (pu1, k1p, True), (pu1, k1o, True), (k1p, k1, True), (k1p, pr1, True), (k1p, k1p, True), (k1p, k1o, True), (k1o, k1, True), (k1o, pr1, True), (k1o, k1p, True), (k1o, k1o, True),
		(k2, k2, True), (k2, pr2, True), (k2, k2p, True), (k2, k2o, True), (pu2, k2, True), (pu2, pr2, True), (pu2, k2p, True), (pu2, k2o, True), (k2p, k2, True), (k2p, pr2, True), (k2p, k2p, True), (k2p, k2o, True), (k2o, k2, True), (k2o, pr2, True), (k2o, k2p, True), (k2o, k2o, True),
		(k1, k2, False), (k1, pr2, False), (k1, k2p, False), (k1, k2o, False), (pu1, k2, False), (pu1, pr2, False), (pu1, k2p, False), (pu1, k2o, False), (k1p, k2, False), (k1p, pr2, False), (k1p, k2p, False), (k1p, k2o, False), (k1o, k2, False), (k1o, pr2, False), (k1o, k2p, False), (k1o, k2o, False),
		(k2, k1, False), (k2, pr1, False), (k2, k1p, False), (k2, k1o, False), (pu2, k1, False), (pu2, pr1, False), (pu2, k1p, False), (pu2, k1o, False), (k2p, k1, False), (k2p, pr1, False), (k2p, k1p, False), (k2p, k1o, False), (k2o, k1, False), (k2o, pr1, False), (k2o, k1p, False), (k2o, k1o, False),
	)
	for test in encryptTests:
		thereAndBackAgain= test[1].decrypt(test[0].encrypt(contents))
		matches= thereAndBackAgain == contents
		if matches != test[2]:
			#print (thereAndBackAgain, contents)
			raise AssertionError("assert:"+str(test)+" - "+values)
	compareTests= (
		(k1, k1, False, True), (k1, k1, True, True), (k1, k1o, False, True), (k1, k1o, True, True), (k1, k1p, False, True), (k1, k1p, True, True),
		(k1, k2, False, False), (k1, k2, True, False), (k1, k2o, False, False), (k1, k2o, True, False), (k1, k2p, False, False), (k1, k2p, True, False),
		(k1, pr1, False, False), (k1, pr1, True, True), (k1, pr2, False, False), (k1, pr2, True, False), (k1, pu1, False, False), (k1, pu1, True, True), (k1, pu2, False, False), (k1, pu2, True, False),
		(k1o, k1, False, True), (k1o, k1, True, True), (k1o, k1o, False, True), (k1o, k1o, True, True), (k1o, k1p, False, True), (k1o, k1p, True, True),
		(k1o, k2, False, False), (k1o, k2, True, False), (k1o, k2o, False, False), (k1o, k2o, True, False), (k1o, k2p, False, False), (k1o, k2p, True, False),
		(k1o, pr1, False, False), (k1o, pr1, True, True), (k1o, pr2, False, False), (k1o, pr2, True, False), (k1o, pu1, False, False), (k1o, pu1, True, True), (k1o, pu2, False, False), (k1o, pu2, True, False),
		(k1p, k1, False, True), (k1p, k1, True, True), (k1p, k1o, False, True), (k1p, k1o, True, True), (k1p, k1p, False, True), (k1p, k1p, True, True), (k1p, k2, False, False),
		(k1p, k2, True, False), (k1p, k2o, False, False), (k1p, k2o, True, False), (k1p, k2p, False, False), (k1p, k2p, True, False), (k1p, pr1, False, False),
		(k1p, pr1, True, True), (k1p, pr2, False, False), (k1p, pr2, True, False), (k1p, pu1, False, False), (k1p, pu1, True, True), (k1p, pu2, False, False), (k1p, pu2, True, False),
		(k2, k1, False, False), (k2, k1, True, False), (k2, k1o, False, False), (k2, k1o, True, False), (k2, k1p, False, False), (k2, k1p, True, False), (k2, k2, False, True),
		(k2, k2, True, True), (k2, k2o, False, True), (k2, k2o, True, True), (k2, k2p, False, True), (k2, k2p, True, True),
		(k2, pr1, False, False), (k2, pr1, True, False), (k2, pr2, False, False), (k2, pr2, True, True), (k2, pu1, False, False), (k2, pu1, True, False), (k2, pu2, False, False), (k2, pu2, True, True),
		(k2o, k1, False, False), (k2o, k1, True, False), (k2o, k1o, False, False), (k2o, k1o, True, False), (k2o, k1p, False, False), (k2o, k1p, True, False),
		(k2o, k2, False, True), (k2o, k2, True, True), (k2o, k2o, False, True), (k2o, k2o, True, True), (k2o, k2p, False, True), (k2o, k2p, True, True),
		(k2o, pr1, False, False), (k2o, pr1, True, False), (k2o, pr2, False, False), (k2o, pr2, True, True), (k2o, pu1, False, False), (k2o, pu1, True, False), (k2o, pu2, False, False), (k2o, pu2, True, True),
		(k2p, k1, False, False), (k2p, k1, True, False), (k2p, k1o, False, False), (k2p, k1o, True, False), (k2p, k1p, False, False), (k2p, k1p, True, False), (k2p, k2, False, True),
		(k2p, k2, True, True), (k2p, k2o, False, True), (k2p, k2o, True, True), (k2p, k2p, False, True), (k2p, k2p, True, True),
		(k2p, pr1, False, False), (k2p, pr1, True, False), (k2p, pr2, False, False), (k2p, pr2, True, True), (k2p, pu1, False, False), (k2p, pu1, True, False), (k2p, pu2, False, False), (k2p, pu2, True, True),
		(pr1, k1, False, False), (pr1, k1, True, True), (pr1, k1o, False, False), (pr1, k1o, True, True), (pr1, k1p, False, False), (pr1, k1p, True, True), (pr1, k2, False, False),
		(pr1, k2, True, False), (pr1, k2o, False, False), (pr1, k2o, True, False), (pr1, k2p, False, False), (pr1, k2p, True, False),
		(pr1, pr1, False, True), (pr1, pr1, True, True), (pr1, pr2, False, False), (pr1, pr2, True, False), (pr1, pu1, False, False), (pr1, pu1, True, True), (pr1, pu2, False, False), (pr1, pu2, True, False),
		(pr2, k1, False, False), (pr2, k1, True, False), (pr2, k1o, False, False), (pr2, k1o, True, False), (pr2, k1p, False, False), (pr2, k1p, True, False),
		(pr2, k2, False, False), (pr2, k2, True, True), (pr2, k2o, False, False), (pr2, k2o, True, True), (pr2, k2p, False, False), (pr2, k2p, True, True),
		(pr2, pr1, False, False), (pr2, pr1, True, False), (pr2, pr2, False, True), (pr2, pr2, True, True), (pr2, pu1, False, False), (pr2, pu1, True, False), (pr2, pu2, False, False), (pr2, pu2, True, True),
		(pu1, k1, False, False), (pu1, k1, True, True), (pu1, k1o, False, False), (pu1, k1o, True, True), (pu1, k1p, False, False), (pu1, k1p, True, True),
		(pu1, k2, False, False), (pu1, k2, True, False), (pu1, k2o, False, False), (pu1, k2o, True, False), (pu1, k2p, False, False), (pu1, k2p, True, False),
		(pu1, pr1, False, False), (pu1, pr1, True, True), (pu1, pr2, False, False), (pu1, pr2, True, False), (pu1, pu1, False, True), (pu1, pu1, True, True), (pu1, pu2, False, False), (pu1, pu2, True, False),
		(pu2, k1, False, False), (pu2, k1, True, False), (pu2, k1o, False, False), (pu2, k1o, True, False), (pu2, k1p, False, False), (pu2, k1p, True, False),
		(pu2, k2, False, False), (pu2, k2, True, True), (pu2, k2o, False, False), (pu2, k2o, True, True), (pu2, k2p, False, False), (pu2, k2p, True, True),
		(pu2, pr1, False, False), (pu2, pr1, True, False), (pu2, pr2, False, False), (pu2, pr2, True, True), (pu2, pu1, False, False), (pu2, pu1, True, False), (pu2, pu2, False, True), (pu2, pu2, True, True),
	)
	for test in compareTests:
		if test[0].equals(test[1], atLeastCompatible= test[2]) != test[3]:
			raise AssertionError("assert:"+str(test)+" - "+values)
	pairTests= (
		(k1, k1, True), (k1, k2, False), (k1, pu1, True), (k1, pu2, False), (k1, pr1, True), (k1, pr2, False), (k1, k1p, True), (k1, k2p, False), (k1, k1o, True), (k1, k2o, False), (k1, None, True),
		(k2, k1, False), (k2, k2, True), (k2, pu1, False), (k2, pu2, True), (k2, pr1, False), (k2, pr2, True), (k2, k1p, False), (k2, k2p, True), (k2, k1o, False), (k2, k2o, True), (k2, None, True),
		(pu1, k1, True), (pu1, k2, False), (pu1, pu1, False), (pu1, pu2, False), (pu1, pr1, True), (pu1, pr2, False), (pu1, k1p, True), (pu1, k2p, False), (pu1, k1o, True), (pu1, k2o, False), (pu1, None, False),
		(pu2, k1, False), (pu2, k2, True), (pu2, pu1, False), (pu2, pu2, False), (pu2, pr1, False), (pu2, pr2, True), (pu2, k1p, False), (pu2, k2p, True), (pu2, k1o, False), (pu2, k2o, True), (pu2, None, False),
		(pr1, k1, True), (pr1, k2, False), (pr1, pu1, True), (pr1, pu2, False), (pr1, pr1, False), (pr1, pr2, False), (pr1, k1p, True), (pr1, k2p, False), (pr1, k1o, True), (pr1, k2o, False), (pr1, None, False),
		(pr2, k1, False), (pr2, k2, True), (pr2, pu1, False), (pr2, pu2, True), (pr2, pr1, False), (pr2, pr2, False), (pr2, k1p, False), (pr2, k2p, True), (pr2, k1o, False), (pr2, k2o, True), (pr2, None, False),
		(k1p, k1, True), (k1p, k2, False), (k1p, pu1, True), (k1p, pu2, False), (k1p, pr1, True), (k1p, pr2, False), (k1p, k1p, True), (k1p, k2p, False), (k1p, k1o, True), (k1p, k2o, False), (k1p, None, True),
		(k2p, k1, False), (k2p, k2, True), (k2p, pu1, False), (k2p, pu2, True), (k2p, pr1, False), (k2p, pr2, True), (k2p, k1p, False), (k2p, k2p, True), (k2p, k1o, False), (k2p, k2o, True), (k2p, None, True),
		(k1o, k1, True), (k1o, k2, False), (k1o, pu1, True), (k1o, pu2, False), (k1o, pr1, True), (k1o, pr2, False), (k1o, k1p, True), (k1o, k2p, False), (k1o, k1o, True), (k1o, k2o, False), (k1o, None, True),
		(k2o, k1, False), (k2o, k2, True), (k2o, pu1, False), (k2o, pu2, True), (k2o, pr1, False), (k2o, pr2, True), (k2o, k1p, False), (k2o, k2p, True), (k2o, k1o, False), (k2o, k2o, True), (k2o, None, True),
	)
	for test in pairTests:
		if None != test[1] and test[0].isPair(test[1]) != test[2]:
			raise AssertionError("assert:"+str(test)+" - "+values)
		elif None == test[1] and test[0].isPair() != test[2]:
			raise AssertionError("assert:"+str(test)+" - "+values)
