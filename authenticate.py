import json
import jwt
import bcrypt
import streamlit as st
from datetime import datetime, timedelta
import extra_streamlit_components as stx
import requests
from hasher import Hasher
from validator import Validator
from utils import generate_random_pw
from exceptions import CredentialsError, ForgotError, RegisterError, ResetError, UpdateError
import smtplib
from email.mime.text import MIMEText

class Authenticate:
    """
    This class will create login, logout, register user, reset password, forgot password, 
    forgot username, and modify user details widgets.
    """
    def __init__(self, credentials: dict, cookie_name: str, key: str, cookie_expiry_days: float=30.0, 
        preauthorized: list=None, validator: Validator=None):
        """
        Create a new instance of "Authenticate".

        Parameters
        ----------
        credentials: dict
            The dictionary of usernames, names, passwords, and emails.
        cookie_name: str
            The name of the JWT cookie stored on the client's browser for passwordless reauthentication.
        key: str
            The key to be used for hashing the signature of the JWT cookie.
        cookie_expiry_days: float
            The number of days before the cookie expires on the client's browser.
        preauthorized: list
            The list of emails of unregistered users authorized to register.
        validator: Validator
            A Validator object that checks the validity of the username, name, and email fields.
        """
        self.credentials = credentials
        self.credentials['usernames'] = {key.lower(): value for key, value in credentials['usernames'].items()}
        self.cookie_name = cookie_name
        self.key = key
        self.cookie_expiry_days = cookie_expiry_days
        self.preauthorized = preauthorized
        self.cookie_manager = stx.CookieManager()
        self.validator = validator if validator is not None else Validator()

        if 'operator' not in st.session_state:
            st.session_state['operator'] = None
        if 'authentication_status' not in st.session_state:
            st.session_state['authentication_status'] = None
        if 'username' not in st.session_state:
            st.session_state['username'] = None
        if 'logout' not in st.session_state:
            st.session_state['logout'] = None
    
    def _token_encode(self) -> str:
        """
        Encodes the contents of the reauthentication cookie.

        Returns
        -------
        str
            The JWT cookie for passwordless authentication.
        """
        
        return jwt.encode({'operator':st.session_state['operator'],
            'username':st.session_state['username'],
            'exp_date':self.exp_date}, self.key, algorithm='HS256')

    def _token_decode(self) -> str:
        """
        Decodes the contents of the reauthentication cookie.

        Returns
        -------
        str
            The decoded JWT cookie for passwordless reauthentication.
        """
        try:
            return jwt.decode(self.token, self.key, algorithms=['HS256'])
        except:
            return False

    def _set_exp_date(self) -> str:
        """
        Creates the reauthentication cookie's expiry date.

        Returns
        -------
        str
            The JWT cookie's expiry timestamp in Unix epoch.
        """
        return (datetime.utcnow() + timedelta(days=self.cookie_expiry_days)).timestamp()

    def _check_pw(self) -> bool:
        """
        Checks the validity of the entered password.

        Returns
        -------
        bool
            The validity of the entered password by comparing it to the hashed password on disk.
        """
        return bcrypt.checkpw(self.password.encode(), 
            self.credentials['usernames'][self.username]['password'].encode())

    def _check_cookie(self):
        """
        Checks the validity of the reauthentication cookie.
        """
        self.token = self.cookie_manager.get(self.cookie_name)
        if self.token is not None:
            self.token = self._token_decode()
            if self.token is not False:
                if not st.session_state['logout']:
                    if self.token['exp_date'] > datetime.utcnow().timestamp():
                        if 'operator' and 'username' in self.token:
                            st.session_state['operator'] = self.token['operator']
                            st.session_state['username'] = self.token['username']
                            st.session_state['authentication_status'] = True
    
    def _check_credentials(self, inplace: bool=True) -> bool:
        """
        Checks the validity of the entered credentials.

        Parameters
        ----------
        inplace: bool
            Inplace setting, True: authentication status will be stored in session state, 
            False: authentication status will be returned as bool.
        Returns
        -------
        bool
            Validity of entered credentials.
        """
        if self.username in self.credentials['usernames']:
            try:
                if self._check_pw():
                    if inplace:
                        st.session_state['operator'] = self.credentials['usernames'][self.username]['operator']
                        self.exp_date = self._set_exp_date()
                        self.token = self._token_encode()
                        self.cookie_manager.set(self.cookie_name, self.token,
                                   expires_at=datetime.now() + timedelta(days=self.cookie_expiry_days))
                        st.session_state['authentication_status'] = True
                        
                    else:
                        return True
                else:
                    if inplace:
                        st.session_state['authentication_status'] = False
                    else:
                        return False
            except Exception as e:
                st.write(e)
        else:
            if inplace:
                st.session_state['authentication_status'] = False
            else:
                return False

    def send_email(self,username: str,email:str,random_password:str):
        email_sender="shaperi@gmail.com"
        email_receiver = email
        
        body = """
        Hi {},
        
        Your temperate password for Sabra Monthly reporting APP is: {}
        Please reset password after login.
        Feel free to contact sli@sabrahealth.com if you have any questions.

        Regards,
        Sabra
        """.format(username,random_password)
        try:
            msg = MIMEText(body)
            msg['From'] = email_sender
            msg['To'] = email_receiver
            msg['Subject'] = "Temperate password for Sabra App"
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(email_sender, "gdwipqjqbtaeixfx")
            server.sendmail(email_sender, email_receiver, msg.as_string())
            server.quit()
            st.success('A temperate password was send to your email: {}.'.format(email))
        except Exception as e:
            st.error("Fail to send email:{}".format(e))

    def Password_Validity(self, s:str):
        l, u, d = 0, 0, 0
        if (len(s) < 8):
            st.error("The length of password should be greater than 8.")
            return False
        elif (len(s) >= 8):
            for i in s:
                # counting lowercase alphabets 
                if (i.islower()):
                    l+=1           
                # counting uppercase alphabets
                if (i.isupper()):
                    u+=1           
                # counting digits
                if (i.isdigit()):
                    d+=1                 

        if l>=1 and u>=1 and d>=1:
            return True
        else:
            st.error("Invalid Password. It should contain at least one uppercase letter, one lower letter and one number")
            return False

    def save_credentials_to_yaml(self, config:dict):
        user_id= '62d4a23f-e25f-4da2-9b52-7688740d9d48'  # shali's user id of onedrive
        mapping_path="Documents/Tenant Monthly Uploading/Tenant Mapping"
        token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        access_token = token_response['access_token']
        # Convert the config dictionary to YAML format
        yaml_content = yaml.dump(config)
    
        # Set the API endpoint and headers for file upload
        api_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/root:/{path}/{"config.yaml"}:/content'
        headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'text/plain' }
    
        # Make the request to upload the file
        response = requests.put(api_url, headers=headers, data=yaml_content)
    
        # Check the status code
        if response.status_code == 200 or response.status_code == 201:
            st.write("File uploaded successfully.")
        else:
            st.write(f"Failed to upload file. Status code: {response.status_code}")
            st.write(f"Response content: {response.content}")
    
    def save_credentials_to_yaml1(self,bucket:str,config:dict):
        s33 = boto3.resource("s3").Bucket(bucket)
        json.dump_s3 = lambda obj, f: s33.Object(key=f).put(Body=json.dumps(obj))
        json.dump_s3(config, "config.yaml") # saves json to s3://bucket/key
        
    def login(self, form_name: str, config, location: str='main') -> tuple:
        """
        Creates a login widget.
        Parameters
        ----------
        form_name: str
            The rendered name of the login form.
        location: str
            The location of the login form i.e. main or sidebar.
        Returns
        -------
        str
            Name of the authenticated user.
        bool
            The status of authentication, None: no credentials entered, 
            False: incorrect credentials, True: correct credentials.
        str
            Username of the authenticated user.
        """

        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if not st.session_state['authentication_status']:
            self._check_cookie()

            if not st.session_state['authentication_status']:
                if location == 'main':
                    login_form = st.form('Login')
                elif location == 'sidebar':
                    login_form = st.sidebar.form('Login')

                login_form.subheader(form_name)
                self.username = login_form.text_input('Username').lower()
                st.session_state['username'] = self.username
                self.password = login_form.text_input('Password', type='password')
                if login_form.form_submit_button('Login'):
                    if len(self.password)>0 and len(self.username)>0:
                        self._check_credentials()
                    else:
                        st.warning('Please enter your username and password')

                # Function to update the value in session state
                def clicked(button_name):
                    st.session_state.clicked[button_name] = True
                col1,col2=st.columns([25,10])
                with col1:
                    st.button('Forgot password', on_click=clicked, args=["forgot_password_button"])
                with col2:
                    st.button('Forgot username', on_click=clicked, args=["forgot_username_button"])

                
                if st.session_state.clicked["forgot_password_button"]:
                    try:
                        username_forgot_pw, email_forgot_password, random_password = self.forgot_password('Forgot password')
                        if username_forgot_pw:
                            self.save_credentials_to_yaml(config)
                            self.send_email(username_forgot_pw,email_forgot_password,random_password)
           
                    except Exception as e:
                        st.error(e)
                        
                # Creating a forgot username widget
                if st.session_state.clicked["forgot_username_button"]:
                    try:
                        username_forgot_username, email_forgot_username = self.forgot_username('Forgot username')
                        if username_forgot_username:
                            st.success("Your username is : "+username_forgot_username)    
                    except Exception as e:
                        st.error(e)
        return st.session_state['operator'], st.session_state['authentication_status'], st.session_state['username']

    def logout(self, button_name: str, location: str='main', key: str=None):
        """
        Creates a logout button.

        Parameters
        ----------
        button_name: str
            The rendered name of the logout button.
        location: str
            The location of the logout button i.e. main or sidebar.
        """
        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if location == 'main':
            button_clicked = st.button(button_name, key=key)
        elif location == 'sidebar':
            button_clicked = st.sidebar.button(button_name, key=key)
        if button_clicked:
            try:
                # Attempt to delete the cookie
                if self.cookie_name in self.cookie_manager.cookies:
                    self.cookie_manager.delete(self.cookie_name)
                else:
                    st.write(f"Cookie '{self.cookie_name}' not found.")
            except Exception as e:
                st.write(f"Error while deleting cookie: {str(e)}")
            st.session_state['logout'] = True
            st.session_state['operator'] = None
            st.session_state['username'] = None
            st.session_state['authentication_status'] = None    
        
    def _update_password(self, username: str, password: str):
        """
        Updates credentials dictionary with user's reset hashed password.

        Parameters
        ----------
        username: str
            The username of the user to update the password for.
        password: str
            The updated plain text password.
        """
        self.credentials['usernames'][username]['password'] = Hasher([password]).generate()[0]
        st.success("Password updated successfully")
    def reset_password(self, username: str, form_name: str, location: str='main') -> bool:
        """
        Creates a password reset widget.

        Parameters
        ----------
        username: str
            The username of the user to reset the password for.
        form_name: str
            The rendered name of the password reset form.
        location: str
            The location of the password reset form i.e. main or sidebar.
        Returns
        -------
        
        str
            The status of resetting the password.
        """
        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if location == 'main':
            reset_password_form = st.form('Reset password')
        elif location == 'sidebar':
            reset_password_form = st.sidebar.form('Reset password')
        
        reset_password_form.subheader(form_name)
        self.username = username.lower()
        self.password = reset_password_form.text_input('Current password', type='password')
        new_password = reset_password_form.text_input('New password', type='password')
        new_password_repeat = reset_password_form.text_input('Repeat password', type='password')

        if reset_password_form.form_submit_button('Reset'):
            if self._check_credentials(inplace=False):
                if len(new_password) > 0:
                    if new_password == new_password_repeat:
                        if self.password != new_password: 
                            self._update_password(self.username, new_password)
                            return True
                        else:
                            raise ResetError('New and current passwords are the same')
                    else:
                        raise ResetError('Passwords do not match')
                else:
                    raise ResetError('No new password provided')
            else:
                raise CredentialsError('password')
    
    def _register_credentials(self, username: str, operator: str, password: str, email: str, preauthorization: bool):
        """
        Adds to credentials dictionary the new user's information.

        Parameters
        ----------
        username: str
            The username of the new user.
        name: str
            The name of the new user.
        password: str
            The password of the new user.
        email: str
            The email of the new user.
        preauthorization: bool
            The preauthorization requirement, True: user must be preauthorized to register, 
            False: any user can register.
        """
        if not self.validator.validate_username(username):
            raise RegisterError('Username is not valid')
        if not self.validator.validate_operator(operator):
            raise RegisterError('operator is not valid')
        if not self.validator.validate_email(email):
            raise RegisterError('Email is not valid')

        self.credentials['usernames'][username] = {'operator': operator, 
            'password': Hasher([password]).generate()[0], 'email': email}
        if preauthorization:
            self.preauthorized['emails'].remove(email)

    def register_user(self, form_name: str, operator:str, config:dict, location: str='main', preauthorization=True) -> bool:
        """
        Creates a register new user widget.

        Parameters
        ----------
        form_name: str
            The rendered name of the register new user form.
        location: str
            The location of the register new user form i.e. main or sidebar.
        preauthorization: bool
            The preauthorization requirement, True: user must be preauthorized to register, 
            False: any user can register.
        Returns
        
        -------
        bool
            The status of registering the new user, True: user registered successfully.
        """
        if preauthorization:
            if not self.preauthorized:
                raise ValueError("preauthorization argument must not be None")
        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if location == 'main':
            register_user_form = st.form('Register user')
        elif location == 'sidebar':
            register_user_form = st.sidebar.form('Register user')

        register_user_form.subheader(form_name)
        new_email = register_user_form.text_input('Email')
        new_username = register_user_form.text_input('Username').lower()
        new_operator = operator
        new_password = register_user_form.text_input('Password', type='password')
        new_password_repeat = register_user_form.text_input('Repeat password', type='password')

        if register_user_form.form_submit_button('Register'):
            if len(new_email) and len(new_username) and len(new_operator) and len(new_password) > 0:
                if new_username not in self.credentials['usernames']:
                    if new_password == new_password_repeat:
                        if preauthorization:
                            if new_email in self.preauthorized['emails']:
                                self._register_credentials(new_username, new_operator, new_password, new_email, preauthorization)
                                self.save_credentials_to_yaml(config)
                                return True
                            else:
                                raise RegisterError('User not preauthorized to register')
                        else:
                            self._register_credentials(new_username, new_operator, new_password, new_email, preauthorization)
                            self.save_credentials_to_yaml(config)
                            return True
                    else:
                        raise RegisterError('Passwords do not match')
                else:
                    raise RegisterError('Username already taken')
            else:
                raise RegisterError('Please enter an email, username, operator, and password')

    def _set_random_password(self, username: str) -> str:
        """
        Updates credentials dictionary with user's hashed random password.

        Parameters
        ----------
        username: str
            Username of user to set random password for.
        Returns
        -------
        str
            New plain text password that should be transferred to user securely.
        """
        self.random_password = generate_random_pw()
        self.credentials['usernames'][username]['password'] = Hasher([self.random_password]).generate()[0]
        return self.random_password

    def forgot_password(self, form_name: str, location: str='main') -> tuple:
        """
        Creates a forgot password widget.

        Parameters
        ----------
        form_name: str
            The rendered name of the forgot password form.
        location: str
            The location of the forgot password form i.e. main or sidebar.
        Returns
        -------
        str
            Username associated with forgotten password.
        str
            Email associated with forgotten password.
        str
            New plain text password that should be transferred to user securely.
        """
        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if location == 'main':
            forgot_password_form = st.form('Forgot password')
        elif location == 'sidebar':
            forgot_password_form = st.sidebar.form('Forgot password')

        forgot_password_form.subheader(form_name)
        username = forgot_password_form.text_input('Username').lower()

        if forgot_password_form.form_submit_button('Submit'):
            if len(username) > 0:
                if username in self.credentials['usernames']:
                    return username, self.credentials['usernames'][username]['email'], self._set_random_password(username)
                else:
                    st.error("Username not found")
                    return False, None, None
            else:
                raise ForgotError('Username not provided')
        return None, None, None

    def _get_username(self, key: str, value: str) -> str:
        """
        Retrieves username based on a provided entry.

        Parameters
        ----------
        key: str
            Name of the credential to query i.e. "email".
        value: str
            Value of the queried credential i.e. "jsmith@gmail.com".
        Returns
        -------
        str
            Username associated with given key, value pair i.e. "jsmith".
        """
        for username, entries in self.credentials['usernames'].items():
            if entries[key] == value:
                return username
        st.error('Email not found')
        return False

    def forgot_username(self, form_name: str, location: str='main') -> tuple:
        """
        Creates a forgot username widget.

        Parameters
        ----------
        form_name: str
            The rendered name of the forgot username form.
        location: str
            The location of the forgot username form i.e. main or sidebar.
        Returns
        -------
        str
            Forgotten username that should be transferred to user securely.
        str
            Email associated with forgotten username.
        """
        if location not in ['main', 'sidebar']:
            raise ValueError("Location must be one of 'main' or 'sidebar'")
        if location == 'main':
            forgot_username_form = st.form('Forgot username')
        elif location == 'sidebar':
            forgot_username_form = st.sidebar.form('Forgot username')

        forgot_username_form.subheader(form_name)
        email = forgot_username_form.text_input('Email')

        if forgot_username_form.form_submit_button('Submit'):
            if len(email) > 0:
                return self._get_username('email', email), email
            else:
                raise ForgotError('Email not provided')
        return None, email

    def _update_entry(self, username: str, key: str, value: str):
        """
        Updates credentials dictionary with user's updated entry.

        Parameters
        ----------
        username: str
            The username of the user to update the entry for.
        key: str
            The updated entry key i.e. "email".
        value: str
            The updated entry value i.e. "jsmith@gmail.com".
        """
        self.credentials['usernames'][username][key] = value

    def update_user_details(self, username: str, form_name: str, config: dict, location: str='main') -> bool:
        """
        Creates a update user details widget.

        Parameters
        ----------
        username: str
            The username of the user to update user details for.
        form_name: str
            The rendered name of the update user details form.
        location: str
            The location of the update user details form i.e. main or sidebar.
        Returns
        -------
        
        str
            The status of updating user details.
        """

        self.username = username.lower()
        st.subheader("Your Profile")
        st.write("Username:",self.username)
        st.write("Email:   ",self.credentials['usernames'][username]["email"] )
        st.write("From:    ",self.credentials['usernames'][username]["operator"] )
      

        st.write("")
        st.subheader("Edit Your Profile")
        col1,col2=st.columns(2)
        with col1:
            field = st.selectbox('Select field need to be updated', ['Username', 'Email','Password']).lower()
            if field=='password':
                # Creating a password reset widget
                try:
                    reset_password_form = st.form('Reset password')
                    reset_password_form.subheader('Reset password')    
                    self.password = reset_password_form.text_input('Current password', type='password')
                    new_password = reset_password_form.text_input('New password', type='password')
                    new_password_repeat = reset_password_form.text_input('Repeat password', type='password')

                    if reset_password_form.form_submit_button('Reset'):
                        if self._check_credentials(inplace=False):
                            if len(new_password) > 0:
                                if new_password == new_password_repeat:
                                    if self.password != new_password: 
                                        if self.Password_Validity(new_password):
                                            self._update_password(self.username, new_password)
                                            self.save_credentials_to_yaml(config)
                                            return True                                          
                                    else:
                                        raise ResetError('New and current passwords are the same')
                                else:
                                    raise ResetError('Passwords do not match')
                            else:
                                raise ResetError('No new password provided')
                        else:
                            raise CredentialsError('password')
                except Exception as e:
                    st.error(e)
            else:
                new_value = st.text_input('New {}'.format(field))

                if st.button('Update'):
                    if len(new_value) > 0:
                        if field=="username":
                            if new_value not in self.credentials['usernames'] :
                                if self.validator.validate_username(username):
                                    st.success("Username updated successfully")
                                    self.credentials['usernames'][new_value] = self.credentials['usernames'].pop(self.username)
                                    self.username=new_value
                                    st.session_state['username'] = self.username
                                    self.exp_date = self._set_exp_date()
                                    self.token = self._token_encode()
                                    self.cookie_manager.set(self.cookie_name, self.token,
                                                        expires_at=datetime.now() + timedelta(days=self.cookie_expiry_days))
                                    self.save_credentials_to_yaml(config)
                                    #st.success("Username updated successfully")
                                    return True
                                else:
                                    raise RegisterError('Username is not valid')
                            else:
                                raise RegisterError('Username already be taken')

                        
                        elif field=='email':
                            if new_value != self.credentials['usernames'][self.username][field]:
                                if self.validator.validate_email(new_value):
                                    self._update_entry(self.username, field, new_value)
                                    self.save_credentials_to_yaml(config)
                                    st.success("Email updated successfully")
                                    return True
                                else:
                                    raise RegisterError('New email is not valid')
                            else:
                                raise UpdateError('New and current email are the same')
                    elif len(new_value) == 0:
                        raise UpdateError('New {} not provided'.format(field))
