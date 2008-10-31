import cherrypy
from cherrypy.lib import httpauth


def check_auth(users, encrypt=None, realm=None):
    """If an authorization header contains credentials, return True, else False."""
    if 'authorization' in cherrypy.request.headers:
        # make sure the provided credentials are correctly set
        ah = httpauth.parseAuthorization(cherrypy.request.headers['authorization'])
        if ah is None:
            raise cherrypy.HTTPError(400, 'Bad Request')
        
        if not encrypt:
            encrypt = httpauth.DIGEST_AUTH_ENCODERS[httpauth.MD5]
        
        if callable(users):
            try:
                # backward compatibility
                users = users() # expect it to return a dictionary

                if not isinstance(users, dict):
                    raise ValueError, "Authentication users must be a dictionary"
                
                # fetch the user password
                password = users.get(ah["username"], None)
            except TypeError:
                # returns a password (encrypted or clear text)
                password = users(ah["username"])
        else:
            if not isinstance(users, dict):
                raise ValueError, "Authentication users must be a dictionary"
            
            # fetch the user password
            password = users.get(ah["username"], None)
        
        # validate the authorization by re-computing it here
        # and compare it with what the user-agent provided
        if httpauth.checkResponse(ah, password, method=cherrypy.request.method,
                                  encrypt=encrypt, realm=realm):
            cherrypy.request.login = ah["username"]
            return True
    
        cherrypy.request.login = False
    return False

def basic_auth(realm, users, encrypt=None):
    """If auth fails, raise 401 with a basic authentication header.
    
    realm: a string containing the authentication realm.
    users: a dict of the form: {username: password} or a callable returning a dict.
    encrypt: callable used to encrypt the password returned from the user-agent.
             if None it defaults to a md5 encryption.
    """
    if check_auth(users, encrypt):
        return
    
    # inform the user-agent this path is protected
    cherrypy.response.headers['www-authenticate'] = httpauth.basicAuth(realm)
    
    raise cherrypy.HTTPError(401, "You are not authorized to access that resource") 

def digest_auth(realm, users):
    """If auth fails, raise 401 with a digest authentication header.
    
    realm: a string containing the authentication realm.
    users: a dict of the form: {username: password} or a callable returning a dict.
    """
    if check_auth(users, realm=realm):
        return
    
    # inform the user-agent this path is protected
    cherrypy.response.headers['www-authenticate'] = httpauth.digestAuth(realm)
    
    raise cherrypy.HTTPError(401, "You are not authorized to access that resource") 
 
