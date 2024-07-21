import pandas as pd 
pd.set_option('future.no_silent_downcasting', True)
import numpy as np 
from datetime import datetime, timedelta,date
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import streamlit as st             
import boto3
from io import BytesIO
from io import StringIO
from tempfile import NamedTemporaryFile
import time
import  streamlit_tree_select
import copy
import streamlit.components.v1 as components
from calendar import monthrange,month_abbr
from authenticate import Authenticate
import yaml 
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
from msal import ConfidentialClientApplication
import requests
from itertools import product
from pandas.errors import EmptyDataError
import pytz
import chardet
from pandas.errors import EmptyDataError
s3 = boto3.client('s3')

#---------------------------define parameters--------------------------
st.set_page_config(
   initial_sidebar_state="expanded",  layout="wide")
placeholder = st.empty()
st.title("Sabra HealthCare Monthly Reporting App")
sheet_name_discrepancy="Discrepancy_Review"
bucket_mapping="sabramapping"
bucket_PL="operatorpl"
account_mapping_filename="Account_Mapping.csv"
BPC_pull_filename="BPC_Pull.csv"
entity_mapping_filename ="Entity_Mapping.csv"
discrepancy_filename="Total_Diecrepancy_Review.csv"
monthly_reporting_filename="Total monthly reporting.csv"
operator_list_filename="Operator_list.csv"
BPC_account_filename="Sabra_account_list.csv"
previous_monthes_comparison=2
availble_unit_accounts=["A_ACH","A_IL","A_ALZ","A_SNF","A_ALF","A_BH","A_IRF","A_LTACH","A_SP_HOSP"]
month_dic_word={10:["october","oct"],11:["november","nov"],12:["december","dec"],1:["january","jan"],\
                   2:["february","feb"],3:["march","mar"],4:["april","apr"],\
                   5:["may"],6:["june","jun"],7:["july","jul"],8:["august","aug"],9:["september","sep"]}
month_dic_num={10:["10/","-10","/10","10","_10"],11:["11/","-11","/11","11","_11"],12:["12/","-12","/12","12"],1:["01/","1/","-1","-01","/1","/01"],\
                   2:["02/","2/","-2","-02","/2","/02"],3:["03/","3/","-3","-03","/3","/03"],4:["04/","4/","-4","-04","/4","/04"],\
                   5:["05/","5/","-5","-05","/5","/05"],6:["06/","6/","-06","-6","/6","/06"],\
                   7:["07/","7/","-7","-07","/7","/07"],8:["08/","8/","-8","-08","/8","/08"],9:["09/","9/","-09","-9","/9","/09"]}
year_dic={2023:["2023","23"],2024:["2024","24"],2025:["2025","25"],2026:["2026","26"]} 	    
#client_secret = '1h28Q~Tw-xwTMPW9w0TqjbeaOhkYVDrDQ8VHcbkd'
#One drive authority. Set application details
client_id = 'bc5f9d8d-eb35-48c3-be6d-98812daab3e3'
client_secret='PgR8Q~HZE2q-dmOb2w_9_0VuxfT9VMLt_Lp3Jbce'
tenant_id = '71ffff7c-7e53-4daa-a503-f7b94631bd53'
authority = 'https://login.microsoftonline.com/' + tenant_id
user_id= '62d4a23f-e25f-4da2-9b52-7688740d9d48'  # shali's user id of onedrive
PL_path="Documents/Tenant Monthly Uploading/Tenant P&L"
mapping_path="Documents/Tenant Monthly Uploading/Tenant Mapping"
master_template_path="Documents/Tenant Monthly Uploading/Master Template"

today=date.today()
current_year= today.year
current_month= today.month

# Acquire a token using client credentials flow
app = ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret)

token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
access_token = token_response['access_token']
headers = {'Authorization': 'Bearer ' + access_token,}    

account_mapping_str_col=["Tenant_Account","Tenant_Formated_Account"]
entity_mapping_str_col=["DATE_ACQUIRED","DATE_SOLD_PAYOFF","Sheet_Name_Finance","Sheet_Name_Occupancy","Sheet_Name_Balance_Sheet","Column_Name"]
#directly save the uploaded (.xlsx) file to onedrive
def Upload_to_Onedrive(uploaded_file,path,file_name):
    # Set the API endpoint and headers
    api_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/items/root:/{path}/{file_name}:/content'


    # Ensure the file pointer is at the start
    uploaded_file.seek(0)
    
    # Read the file content as binary data
    file_content = uploaded_file.read()
    
    # Set the Content-Type header for Excel files
    headers.update({'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
    
    
    # Make the request to upload the file
    response = requests.put(api_url, headers=headers, data=file_content)
	
    #response = requests.put(api_url, headers=headers, data=BytesIO(uploaded_file.read()))
    if response.status_code in [200,201]:# or response.status_code==201:
        return True
    else:
        return False

# no cache read csv/excel from onedrive , return dataframe
def detect_encoding(file_content):
    result = chardet.detect(file_content)
    return result['encoding']

def Read_CSV_From_Onedrive(path, file_name,str_col_list=None):
    if str_col_list is None:
        str_col_list = []
    
    # Set the API endpoint and headers for file download
    api_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/root:/{path}/{file_name}:/content'
    
    # Make the request to download the file
    response = requests.get(api_url, headers=headers)
    
    # Check the status code 
    if response.status_code == 200 or response.status_code == 201:
        # Content of the file is available in response.content
        try:
            file_content = response.content
            detected_encoding = detect_encoding(file_content)
            dtype_dict = {col: str for col in str_col_list}
            if file_name.lower().endswith(".csv"):
                # Try reading the CSV with the detected encoding
                try:
                    df = pd.read_csv(BytesIO(file_content), encoding=detected_encoding, on_bad_lines='skip',dtype=dtype_dict)
                except UnicodeDecodeError:
                    # If detected encoding fails, try common fallback encodings
                    try:
                        df = pd.read_csv(BytesIO(file_content), encoding='utf-8', on_bad_lines='skip',dtype=dtype_dict)
                    except UnicodeDecodeError:
                        df = pd.read_csv(BytesIO(file_content), encoding='latin1', on_bad_lines='skip',dtype=dtype_dict)
            elif file_name.lower().endswith(".xlsx"):
                df = pd.read_excel(BytesIO(file_content),dtype=dtype_dict)
            return df
        except EmptyDataError:
            return False
        except pd.errors.ParserError as e:
            return False
        except Exception as e:
            return False
    else:
        st.write(f"Failed to download file. Status code: {response.status_code}")
        st.write(f"Response content: {response.content}")
        return False


# no cache, save a dataframe to OneDrive 
def Save_as_CSV_Onedrive(df,path,file_name):   
    try:
        df=df[list(filter(lambda x: x!="index" and "Unnamed:" not in x,df.columns))]
        csv_string = df.to_csv(index=False)
	# Define your Microsoft Graph API endpoint, user ID, file path, and headers
        api_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/items/root:/{path}/{file_name}:/content'    
        response = requests.put(api_url, headers=headers, data=BytesIO(csv_string.encode()))
        # Check the response
        if response.status_code == 200:
            return True
        else:
            return False
    except:
        return False


# For updating account_mapping, entity_mapping, reporting_month_data, only for operator use
def Update_File_Onedrive(path,file_name,new_data,operator,entity_list=None,str_col_list=None):  # replace original data
    if entity_list==None:
        entity_list=[]    
    original_data=Read_CSV_From_Onedrive(path,file_name,str_col_list)
    new_data=new_data.reset_index(drop=False)
    if  isinstance(original_data, pd.DataFrame):
        if "TIME" in original_data.columns and "TIME" in new_data.columns:
            original_data.TIME = original_data.TIME.astype(str)
            months_of_new_data=new_data["TIME"].unique()
            if len(entity_list)==0:
                # remove original data by operator and month
                original_data = original_data.drop(original_data[(original_data['Operator'] == operator)&(original_data['TIME'].isin(months_of_new_data))].index)
            elif len(entity_list)>0:  # only updated data for given entity_list
            	# remove original data by operator and month and entity
                original_data = original_data.drop(original_data[(original_data['Operator'] == operator)&(original_data['TIME'].isin(months_of_new_data))&(original_data['ENTITY'].isin(entity_list))].index)
                new_data=new_data[new_data["ENTITY"].isin(entity_list)]
                st.write("new data",new_data) 
        elif "TIME" not in original_data.columns and "TIME" not in new_data.columns:
            if len(entity_list)==0:
                original_data = original_data.drop(original_data[original_data['Operator'] == operator].index)
            elif len(entity_list)>0:
            	# remove original data by operator and month and entity
                original_data = original_data.drop(original_data[(original_data['Operator'] == operator)&(original_data['ENTITY'].isin(entity_list))].index)
	    		
        # append new data to original data
        new_columns_name=list(filter(lambda x:str(x).upper()!="INDEX",new_data.columns))
        updated_data = pd.concat([original_data,new_data])
        updated_data=updated_data[new_columns_name]
    elif original_data is None:
        updated_data=new_data.reset_index(drop=False)
        new_columns_name=list(filter(lambda x:str(x).upper()!="INDEX",new_data.columns))
        updated_data=updated_data[new_columns_name]	
    return Save_as_CSV_Onedrive(updated_data,path,file_name)  # return True False


# no cache
def Read_CSV_FromS3(bucket,key):
    file_obj = s3.get_object(Bucket=bucket, Key=key)
    data = pd.read_csv(BytesIO(file_obj['Body'].read()),header=0)
    return data

# no cache,   save a dataframe to S3 
def Save_CSV_ToS3(data,bucket,key):   
    try:
        data=data[list(filter(lambda x: x!="index" and "Unnamed:" not in x,data.columns))]
        csv_buffer = StringIO()
        data.to_csv(csv_buffer)
        s3_resource = boto3.resource('s3')
        s3_resource.Object(bucket,key).put(Body=csv_buffer.getvalue())
        return True
    except:
        return False
	     
# no Cache , directly save the uploaded .xlsx file to S3 
def Upload_File_toS3(uploaded_file, bucket, key):  
    try:
        s3.upload_fileobj(uploaded_file, bucket, key)
        return True
    except:
        return False  

def Format_Value(column):
    def format_value(x):
        if pd.isna(x) or x == None or x == " ":
            return None
        elif x == 0:
            return None
        elif isinstance(x, float):
            return round(x, 1)
        return x
    
    return column.apply(format_value)


# Function to update the value in session state
def clicked(button_name):
    st.session_state.clicked[button_name] = True

# No cache
def Initial_Mapping(operator):
    BPC_pull=Read_CSV_From_Onedrive(mapping_path,BPC_pull_filename)
    BPC_pull=BPC_pull[BPC_pull["Operator"]==operator]
    BPC_pull=BPC_pull.set_index(["ENTITY","Sabra_Account"])
    BPC_pull.columns=list(map(lambda x :str(x), BPC_pull.columns))
	
    account_mapping_all = Read_CSV_From_Onedrive(mapping_path,account_mapping_filename,account_mapping_str_col)
    account_mapping = account_mapping_all.loc[account_mapping_all["Operator"]==operator]
    if account_mapping.shape[0]==1:# and account_mapping.loc[:,"Sabra_Account"][0]=='Template':
        account_mapping = account_mapping_all.loc[account_mapping_all["Operator"]=="Template"]
        account_mapping.loc[:,"Operator"]=operator
    account_mapping.loc[:, 'Sabra_Account'] = account_mapping['Sabra_Account'].apply(lambda x: x.upper().strip() if  pd.notna(x) else x)
    account_mapping.loc[:, 'Sabra_Second_Account'] = account_mapping['Sabra_Second_Account'].apply(lambda x:  x.upper().strip() if pd.notna(x) else x)
    account_mapping.loc[:, "Tenant_Formated_Account"] = account_mapping["Tenant_Account"].apply(lambda x: x.upper().strip() if pd.notna(x) else x)
    account_mapping=account_mapping[["Operator","Sabra_Account","Sabra_Second_Account","Tenant_Account","Tenant_Formated_Account","Conversion"]] 

    entity_mapping=Read_CSV_From_Onedrive(mapping_path,entity_mapping_filename,entity_mapping_str_col)
    entity_mapping=entity_mapping.reset_index(drop=True)
    entity_mapping=entity_mapping[entity_mapping["Operator"]==operator]
    entity_mapping=entity_mapping.set_index("ENTITY")
    entity_mapping['DATE_ACQUIRED'] = entity_mapping['DATE_ACQUIRED'].astype(str)
    entity_mapping['DATE_SOLD_PAYOFF'] = entity_mapping['DATE_SOLD_PAYOFF'].astype(str)
    return BPC_pull,entity_mapping,account_mapping

	
# Intialize a list of tuples containing the CSS styles for table headers
th_props = [('font-size', '14px'), ('text-align', 'left'),
            ('font-weight', 'bold'),('color', '#6d6d6d'),
            ('background-color', '#eeeeef'), ('border','1px solid #eeeeef')]

# Intialize a list of tuples containing the CSS styles for table data
td_props = [('font-size', '14px'), ('text-align', 'left')]

# Aggregate styles in a list
styles = [dict(selector="th", props=th_props),dict(selector="td", props=td_props)]


def left_align(s, props='text-align: left;'):
    return props
css='''
<style>
    section.main>div {
        padding-bottom: 1rem;
    }
    [data-testid="table"]>div>div>div>div>div {
        overflow: auto;
        height: 20vh;
    }
</style>
'''
st.markdown(css, unsafe_allow_html=True)

# convert column number into letter for CVS file 0-A, 1-B,2-c
def colnum_letter(col_number):
    letter = ""
    col_number+=1
    while col_number > 0:
        col_number, remainder = divmod(col_number - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter 
	
@st.cache_data
def Create_Tree_Hierarchy(bucket_mapping):
    #Create Tree select hierarchy
    parent_hierarchy_main=[{'label': "No need to map","value":"No need to map"}]
    parent_hierarchy_second=[{'label': "No need to map","value":"No need to map"}]
    BPC_Account = Read_CSV_From_Onedrive(mapping_path,BPC_account_filename)
    for category in BPC_Account[BPC_Account["Type"]=="Main"]["Category"].unique():
        children_hierarchy=[]
        for account in BPC_Account[(BPC_Account["Category"]==category)&(BPC_Account["Type"]=="Main")]["Sabra_Account_Full_Name"]:
            dic={"label":account,"value":BPC_Account[(BPC_Account["Sabra_Account_Full_Name"]==account)&(BPC_Account["Type"]=="Main")]["BPC_Account_Name"].item()}
            children_hierarchy.append(dic)
        dic={"label":category, "value":category, "children":children_hierarchy}
        parent_hierarchy_main.append(dic)
        
    for category in BPC_Account[BPC_Account["Type"]=="Second"]["Category"].unique():
        children_hierarchy=[]
        for account in BPC_Account[(BPC_Account["Category"]==category)&(BPC_Account["Type"]=="Second")]["Sabra_Account_Full_Name"]:
            dic={"label":account,"value":BPC_Account.loc[(BPC_Account["Sabra_Account_Full_Name"]==account)&(BPC_Account["Type"]=="Second")]["BPC_Account_Name"].item()}
            children_hierarchy.append(dic)
        dic={"label":category,"value":category,"children":children_hierarchy}
        parent_hierarchy_second.append(dic)
    
    BPC_Account=BPC_Account[["BPC_Account_Name","Sabra_Account_Full_Name","Category"]]
    return parent_hierarchy_main,parent_hierarchy_second,BPC_Account
parent_hierarchy_main,parent_hierarchy_second,BPC_Account=Create_Tree_Hierarchy(bucket_mapping)

#-----------------------------------------------functions---------------------------------------------
def ChangeWidgetFontSize(wgt_txt, wch_font_size = '12px'):
    htmlstr = """<script>var elements = window.parent.document.querySelectorAll('*'), i;
                    for (i = 0; i < elements.length; ++i) { if (elements[i].innerText == |wgt_txt|) 
                        { elements[i].style.fontSize='""" + wch_font_size + """';} } </script>  """
    htmlstr = htmlstr.replace('|wgt_txt|', "'" + wgt_txt + "'")
    components.html(f"{htmlstr}", height=0, width=0)


# Parse the df and get filter widgets based for provided columns
def filters_widgets(df, columns,location="Vertical"):
    filter_widgets = st.container()
    with filter_widgets.form(key="data_filters"):
        if location=='Horizontal':
            cols = st.columns(len(columns))   
            for i, x in enumerate(cols):
                if location=='Horizontal':
                    user_input = x.multiselect(
                    label=str(columns[i]),
                    options=df[columns[i]].unique().tolist(),
                    key=str(columns[i]))
                    if user_input:
                        df = df[df[columns[i]].isin(user_input)]  
        else:  
            for column in columns:
                user_input = st.multiselect(
                    label=str(column),
                    options=df[column].unique().tolist(),
                    key=str(column))
                if user_input:
                    df = df[df[columns[i]].isin(user_input)]                      
        submit_button = st.form_submit_button("Apply Filters")
        if submit_button:
            return df
        else:
            return df
		
def Identify_Tenant_Account_Col(PL,sheet_name,sheet_type_name,account_pool,pre_max_match_col):
    #search tenant account column in P&L, return col number of tenant account	
    if pre_max_match_col!=10000 and pre_max_match_col<PL.shape[1]:
        #check if pre_max_match is the tenant_col
        candidate_col=list(map(lambda x: str(x).strip().upper() if not pd.isna(x) and isinstance(x, str) else x,PL.iloc[:,pre_max_match_col]))
        match=[x in candidate_col for x in account_pool]
        if len(match)>0 and sum(x for x in match)/len(account_pool)>0.5:
            return pre_max_match_col
    max_match=0
    for tenantAccount_col_no in range(0,min(15,PL.shape[1])):
        candidate_col=list(map(lambda x: str(x).strip().upper() if not pd.isna(x) and isinstance(x, str) else x,PL.iloc[:,tenantAccount_col_no]))
        #find out how many tenant accounts match with account_mapping
        match=[x in candidate_col for x in account_pool]

        match_count=sum(x for x in match)
        if len(match)>0 and match_count>max_match:
            max_match_col=tenantAccount_col_no
            max_match=match_count

    if max_match>0:
        return max_match_col     
    st.error("Fail to identify tenant accounts column in {} sheet —— {}".format(sheet_type_name,sheet_name))
    st.stop()


def download_report(df,button_display):
    download_file=df.to_csv(index=False).encode('utf-8')
    return st.download_button(label="Download "+button_display,data=download_file,file_name=button_display+".csv",mime="text/csv")
 
def Get_Year(single_string):
    for Year in year_dic.keys():
        for Year_keyword in year_dic[Year]:
            if Year_keyword in single_string:
                #st.write("single_string",single_string,"return",Year,Year_keyword)
                return Year,Year_keyword
    return 0,""

def Get_Month_Year(single_string):
    if single_string!=single_string or pd.isna(single_string):
        return 0,0
    if isinstance(single_string, datetime):
        return int(single_string.month),int(single_string.year)

    if isinstance(single_string, (int,float)) and single_string not in year_dic.keys():
        #st.write("single_string",single_string,"return 0,0")
        return 0,0
    single_string=str(single_string).lower()
    year,year_num=Get_Year(single_string)
    if year!=0:
        single_string=single_string.replace(year_num,"")
        if single_string=="":
            return 0,year
    single_string=single_string.replace("30","").replace("31","").replace("29","").replace("28","")
    for month_i in month_dic_word.keys() :#[01,02,03...12]
        for  month_word in month_dic_word[month_i]: #['december','dec',"nov",...]
            #st.write("single_string",single_string)
            #st.write("month_word in single_string",month_word in single_string)
            if month_word in single_string:  # month is words ,like Jan Feb... year is optional

                remaining=single_string.replace(month_word,"").replace("/","").replace("-","").replace(" ","").replace("_","").replace("asof","").replace("actual","")
                
                #if there are more than 3 other char in the string, this string is not month 
                if len(remaining)>=3:
                    return 0,0
                else:   
                    return month_i,year
        # didn't detect month words in above code, check number format: 3/31/2024, 3/2023...
	# if there is no year , skip
        if year==0:
            continue   
        
        for  month_num in month_dic_num[month_i]: 
            if month_num in single_string:  # month is number ,like 01/, 02/,   year is Mandatory
                remaining=single_string.replace(month_num,"").replace("/","").replace("-","").replace(" ","").replace("_","").replace("asof","").replace("actual","")
                #if there are more than 3 other char in the string, this string is not month 
                if len(remaining)>=3:
                    return 0,0
                else:   
                    return month_i,year	
    # didn't find month. return month as 0
    return 0,0   

# add year to month_header: identify current year/last year giving a list of month
def Fill_Year_To_Header(PL,month_row_index,full_month_header,sheet_name,reporting_month):

    #remove rows with nan tenant account
    nan_index=list(filter(lambda x:pd.isna(x) or x=="nan" or x=="" or x==" " or x==0 ,PL.index))
    column_mask = [all(val == 0 or not isinstance(val, (int, float)) or pd.isna(val) for val in PL.drop(nan_index).iloc[month_row_index:, i]) for i in range(PL.drop(nan_index).shape[1])]
   
    # Apply the mask to set these columns to NaN in the row specified by month_row_index
    full_month_header=[0 if column_mask[i] else full_month_header[i] for i in range(len(full_month_header))]
    month_list=list(filter(lambda x:x!=0,full_month_header))
    month_len=len(month_list)
    full_year_header=[0] * len(full_month_header)
    if month_len==1:
        year=reporting_month[0:4]
        PL_date_header= [f"{year}{month:02d}" if month!=0 else 0 for month in full_month_header]
        return PL_date_header

	    
    add_year=month_list
    last_year=current_year-1
    year_change=0  
	
    inv=[int(month_list[month_i+1])-int(month_list[month_i]) for month_i in range(month_len-1) ]
    #st.write("inv",inv)
    ascending_check=sum([x in [1,-11] for x in inv])
    descending_check=sum([x in [-1,11] for x in inv])
    reporting_month_date=datetime.strptime(str(reporting_month[4:6])+"/01/"+str(reporting_month[0:4]),'%m/%d/%Y').date()   
    #month decending  , month_list[0]<today.month 
    if descending_check>0 and descending_check>ascending_check: 
        date_of_assumption=datetime.strptime(str(month_list[0])+"/01/"+str(current_year),'%m/%d/%Y').date()
        if date_of_assumption==reporting_month_date:	
            report_year_start=current_year
        elif date_of_assumption<today and date_of_assumption.month<today.month:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(month_len):
            add_year[i]=report_year_start-year_change
            if i<month_len-1 and add_year[i+1]==12:
                year_change+=1
            
    # month ascending  
    elif ascending_check>0 and ascending_check> descending_check: 
        date_of_assumption=datetime.strptime(str(month_list[-1])+"/01/"+str(current_year),'%m/%d/%Y').date() 
        if date_of_assumption==reporting_month_date:
            report_year_start=current_year
        elif date_of_assumption<today:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(-1,month_len*(-1)-1,-1):
            add_year[i]=report_year_start-year_change
            if i>month_len*(-1) and add_year[i-1]==12:
                year_change+=1
    #month decending 	    
    elif (month_list[0]>month_list[1] and month_list[0]!=12) or (month_list[0]==1 and month_list[1]==12):
        date_of_assumption=datetime.strptime(str(month_list[0])+"/01/"+str(current_year),'%m/%d/%Y').date()
        if date_of_assumption<today and date_of_assumption.month<today.month:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(month_len):
            add_year[i]=report_year_start-year_change
            if i<month_len-1 and add_year[i+1]==12:
                year_change+=1
     # month ascending
    elif (month_list[0]<month_list[1] and month_list[0]!=12) or (month_list[0]==12 and month_list[1]==1): 
        date_of_assumption=datetime.strptime(str(month_list[-1])+"/01/"+str(current_year),'%m/%d/%Y').date()    
        if date_of_assumption<today:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(-1,month_len*(-1)-1,-1):
            add_year[i]=report_year_start-year_change
            if i>month_len*(-1) and add_year[i-1]==12:
                year_change+=1
    else:
        st.error("Fail to identify Year in sheet {}, please add the year for the month and re-upload.".format(sheet_name))
        st.stop()
    j=0
  
 
    for i in range(len(full_month_header)):
        if full_month_header[i]!=0:
            full_year_header[i]=add_year[j]
            j+=1
    PL_date_header= [f"{year}{month:02d}" if year!=0 else 0 for year, month in zip(full_year_header, full_month_header)]
    return PL_date_header
	
@st.cache_data
def Check_Available_Units(check_patient_days,reporting_month):
    month_days=monthrange(int(reporting_month[:4]), int(reporting_month[4:]))[1]
    problem_properties=[]
    zero_patient_days=[]
    for property_i in reporting_month_data["Property_Name"].unique():
        try:
            patient_day_i=check_patient_days.loc[(property_i,"Patient Days"),reporting_month]
        except:
            patient_day_i=0
        try:
            operating_beds_i=check_patient_days.loc[(property_i,"Operating Beds"),reporting_month]
        except:
            operating_beds_i=0
        if patient_day_i>0 and operating_beds_i*month_days>patient_day_i:
            continue
        elif operating_beds_i>0 and patient_day_i>operating_beds_i*month_days:
            st.error("Error：The number of patient days for {} exceeds its available days (Operating Beds * {}). This will result in incorrect occupancy.".format(property_i,month_days))
            problem_properties.append(property_i)
        elif operating_beds_i==0 and patient_day_i==0:
            zero_patient_days.append(property_i)
        elif patient_day_i==0 and operating_beds_i>0:
            st.error("Error: {} is missing patient days. If this facility is not currently functioning or in operation, please remove the number of operating beds associated with it.".format(property_i))
            problem_properties.append(property_i)     
        elif patient_day_i>0 and operating_beds_i==0:
            st.error("Error：{} is missing operating beds. With {} patient days, this will result in incorrect occupancy.".format(property_i,int(patient_day_i)))
            problem_properties.append(property_i) 
    miss_all_A_unit=False
    if len(problem_properties)>0:
        check_patient_days_display=check_patient_days.loc[(problem_properties,slice(None)),reporting_month].reset_index(drop=False)
        check_patient_days_display=check_patient_days_display.pivot_table(index=["Property_Name"],columns="Category", values=reporting_month,aggfunc='last')
        if "Operating Beds" not in check_patient_days_display.columns:
            check_patient_days_display["Operating Beds"]=0
            miss_all_A_unit=True
        st.dataframe(check_patient_days_display.style.map(color_missing, subset=["Patient Days","Operating Beds"]).format(precision=0, thousands=",").hide(axis="index"),
		    column_config={
			        "Property_Name": "Property",
		                "Patient Days": "Patient Days",
		                "Operating Beds": "Operating Beds"},
			    hide_index=True)
    if miss_all_A_unit==False:
        BPC_pull_temp=BPC_pull.reset_index(drop=False)
        onemonth_before_reporting_month=max(list(filter(lambda x: str(x)[0:2]=="20" and str(x)<str(reporting_month),BPC_pull.columns)))
        previous_available_unit=BPC_pull_temp.loc[BPC_pull_temp["Sabra_Account"].isin(availble_unit_accounts),["Property_Name",onemonth_before_reporting_month]]  
        previous_available_unit[["Property_Name",onemonth_before_reporting_month]].groupby(["Property_Name"]).sum()
        previous_available_unit=previous_available_unit.reset_index(drop=False)[["Property_Name",onemonth_before_reporting_month]]
        check_patient_days=check_patient_days.reset_index(drop=False)
        Unit_changed=pd.merge(previous_available_unit, check_patient_days.loc[check_patient_days['Category'] == 'Operating Beds',["Property_Name",reporting_month]],on=["Property_Name"], how='left')
        Unit_changed["Delta"]=Unit_changed[onemonth_before_reporting_month]-Unit_changed[reporting_month]
        Unit_changed=Unit_changed.loc[(Unit_changed["Delta"]!=0)&(Unit_changed[reporting_month]!=0)&(pd.isna(Unit_changed[reporting_month])),]
        if len(Unit_changed)>0:
            st.warning("The number of operating beds for the properties listed below have changed compared to the previous reporting month.")
            st.warning("Please double-check if these changes are accurate.")
            st.dataframe(Unit_changed.style.map(color_missing, subset=["Delta"]).format(precision=0, thousands=",").hide(axis="index"),
		    column_config={
			        "Property_Name": "Property",
			        onemonth_before_reporting_month:onemonth_before_reporting_month+" Operating beds",
		                 reporting_month:reporting_month+" Operating beds",
		                 "Delta": "Changed"},
			    hide_index=True)

@st.cache_data
def Identify_Month_Row(PL,sheet_name,pre_date_header,tenantAccount_col_no): 
    #st.write("PL,PL.index,PL.columns",PL,PL.index,PL.columns,PL.shape[1],PL[1])
    #pre_date_header is the date_header from last PL. in most cases all the PL has same date_header, so check it first
    if len(pre_date_header[2])!=0:
        if PL.iloc[pre_date_header[1],:].equals(pre_date_header[2]):
            return pre_date_header
    PL_col_size=PL.shape[1]
    tenant_account_row_mask = PL.index.str.upper().str.strip().isin([account for account in account_mapping['Tenant_Formated_Account'] if account != 'NO NEED TO MAP'])
    tenant_account_row_mask=tenant_account_row_mask.tolist()
    #first_tenant_account_row is the row number for the first tenant account (except for no need to map)
    first_tenant_account_row=tenant_account_row_mask.index(max(tenant_account_row_mask))

    PL_temp=PL.loc[tenant_account_row_mask]
    #valid_col_mask labels all the columns that ([False, False, True,...])
	#1. on the right of tenantAccount_col_no 
	#2.contain numeric value 
	#3. not all 0 or nan in tenant_account_row. 

    valid_col_mask = PL_temp.apply(\
    lambda x: ( pd.to_numeric(x, errors='coerce').notna().any() and \
           not all((v == 0 or pd.isna(v) or isinstance(v, str) or not isinstance(v, (int, float))) for v in x)\
         ) if PL_temp.columns.get_loc(x.name) > tenantAccount_col_no else False, axis=0)

    valid_col_index=[i for i, mask in enumerate(valid_col_mask) if mask]
    # nan_num_column is the column whose value is nan or 0 for PL.drop(nan_index)
    #nan_num_column = [all(val == 0 or pd.isna(val) or not isinstance(val, (int, float)) for val in PL.drop(nan_index).iloc[:, i]) for i in range(PL.drop(nan_index).shape[1])]
    month_table=pd.DataFrame(0,index=range(first_tenant_account_row), columns=range(PL_col_size))
    year_table=pd.DataFrame(0,index=range(first_tenant_account_row), columns=range(PL_col_size))

    for row_i in range(first_tenant_account_row): # only search month/year above the first tenant account row
        for col_i in valid_col_index:  # only search the columns that contain numberic data and on the right of tenantAccount_col_no
            month_table.iloc[row_i,col_i],year_table.iloc[row_i,col_i]=Get_Month_Year(PL.iloc[row_i,col_i]) 
    
    max_len=0
    candidate_date=[]
    month_count = month_table.apply(lambda row: (row != 0).sum(), axis=1).tolist()
    year_count = year_table.apply(lambda col: (col != 0).sum(), axis=0).tolist()

    if not all(x==0 for x in month_count):
        month_sort_index = np.argsort(np.array(month_count))
        for month_index_i in range(-1,-10,-1): 
            #month_sort_index[-1] is the index number of month_count in which has max month count
            #month_row_index is also the index/row number of PL
            month_row_index=month_sort_index[month_index_i]
            month_row=list(month_table.iloc[month_row_index,])
            month_list=list(filter(lambda x:x!=0,month_row))
            month_len=len(month_list)
            max_match_year=0
            for i in [0,1,-1]:  # identify year in corresponding month row
                if month_row_index+i>=0 and month_row_index+i<year_table.shape[0]:
                    year_row=list(year_table.iloc[month_row_index+i,])
                    year_match = [year for month, year in zip(month_row, year_row) if month!= 0 and year!=0]
                  
                    if len(year_match)==month_len:
                        year_table.iloc[month_row_index,:] = [year_table.iloc[month_row_index+i,j] if month != 0 else 0 for j, month in enumerate(month_row)]
                        max_match_year=len(year_match)
                        break
                    elif len(year_match)<month_len and len(year_match)>max_match_year:
                        year_table.iloc[month_row_index,:] = [year_table.iloc[month_row_index+i,j] if month != 0 else 0 for j, month in enumerate(month_row)]
                        max_match_year=len(year_match)
                    else:
                        continue
  
            if month_count[month_row_index]>1:   # if there are more than one month in the header	    
	        #check month continuous, there are at most two types of differences in the month list which are in 1,-1,11,-11 
                inv=[int(month_list[month_i+1])-int(month_list[month_i]) for month_i in range(month_len-1) ]
                continuous_check_bool=[x in [1,-1,11,-11] for x in inv]
                len_of_continuous=sum(continuous_check_bool)
                len_of_non_continuous=len(continuous_check_bool)-len_of_continuous
                if  len_of_continuous==len(continuous_check_bool) \
		or len_of_continuous>=10 \
		or (len_of_continuous<10 and len_of_continuous>=3 and len_of_non_continuous<=2) \
		or (len_of_continuous<=2 and len_of_continuous>=1 and len_of_non_continuous==1)\
                or all(x == 0 for x in inv) :
		    #check the corresponding year
                    if max_match_year>0:
                        PL_date_header=year_table.iloc[month_row_index,].apply(lambda x:str(int(x)))+\
                                                      month_table.iloc[month_row_index,].apply(lambda x:"" if x==0 else "0"+str(int(x)) if x<10 else str(int(x)))
                        
                        if reporting_month not in list(PL_date_header):
                            #year_table.iloc[month_row_index,]=Fill_Year_To_Header(list(month_table.iloc[month_row_index,]),sheet_name,reporting_month)
                            PL_date_header=Fill_Year_To_Header(PL,month_row_index,list(month_table.iloc[month_row_index,]),sheet_name,reporting_month)
                            #st.write("PL_date_header",PL_date_header)         
                    elif max_match_year==0:  # there is no year for all the months
		        #fill year to month
                        #st.write("PL",PL,"month_row_index",month_row_index,"list(month_table.iloc[month_row_index,])",list(month_table.iloc[month_row_index,]),"sheet_name",sheet_name)
                        PL_date_header=Fill_Year_To_Header(PL,month_row_index,list(month_table.iloc[month_row_index,]),sheet_name,reporting_month)
                     
                        original_header=PL.iloc[month_row_index,]
                        PL_date_header_list=list(PL_date_header)
                   
                        d_str = ''
                        for i in range(len(PL_date_header)):
                            if PL_date_header[i]==0 or PL_date_header[i]=="0":
                                continue
                            else:
                                date=str(PL_date_header[i][4:6])+"/"+str(PL_date_header[i][0:4])
                                d_str +=",  "+str(PL.iloc[month_row_index,i])+" — "+ date
                
                        st.warning("Fail to identify **'Year'** for the date header in sheet '{}'. Filled year as:".format(sheet_name))
                        st.markdown(d_str[1:])
                    count_reporting_month=list(PL_date_header).count(reporting_month)
                   
                    if count_reporting_month==0: # there is no reporting_month
                       continue
                    elif count_reporting_month>1:
                        st.error("There are more than one '{}/{}' header in sheet '{}'. Only one is allowed to identify the data column of '{}/{}'".\
			     format(reporting_month[4:6],reporting_month[0:4],sheet_name,reporting_month[4:6],reporting_month[0:4]))
                    elif count_reporting_month==1:  # there is only one reporting month in the header
                        return PL_date_header,month_row_index,PL.iloc[month_row_index,:]	
		
                else:
                    continue
			
        
            # only one month in header, all the rows that have multiple months were out
            elif month_count[month_row_index]==1:
                col_month = next((col_no for col_no, val_month in enumerate(month_table.iloc[month_row_index, :]) if val_month != 0), 0)
                if month_table.iloc[month_row_index,col_month]!=int(reporting_month[4:]):
                    continue
		#if there are two month headers in the same column, conintue	
                if candidate_date!=[] and any(col_month == candidate_date_i[-1] for candidate_date_i in candidate_date):
                    continue
			
                PL_date_header= [reporting_month if x!=0 else 0 for x in month_table.iloc[month_row_index,:]]
                candidate_date.append([PL_date_header,month_row_index,PL.iloc[month_row_index,:],col_month] )
                continue

    if len(candidate_date)>1:
        #st.write(",".join([sublist[-1]+1 for sublist in candidate_date]))
        st.error("We detected {} date headers in sheet——'{}'. Please ensure there's only one date header for the data column.".format(len(candidate_date),sheet_name))
        st.stop()
    elif len(candidate_date)==1:	    
        return candidate_date[0][0:3]

    # there is no month/year in PL
    elif len(candidate_date)==0: 
	# if there is only one column contains numeric data, identify this column as reporting month     
	# search "current month" as reporting month

        if len(valid_col_index) > 1 or len(valid_col_index) ==0:
	    # search "current month" as reporting month
            current_month_cols=[]

            for col_i in valid_col_index:
                st.write(PL,valid_col_index)
                column = PL.iloc[0:first_tenant_account_row, col_i]
                st.write("column",column)
                if column.astype(str).str.contains('current month', case=False, na=False).any():
                    current_month_cols.append(col_i)
                    current_month_rows = column.index[column.astype(str).str.contains('current month', case=False, na=False)][0]
                    st.write("column",column,"current_month_rows",current_month_rows)
            if len(current_month_cols)==1:
                PL_date_header = [0] * PL.shape[1]
                PL_date_header[current_month_cols[0]] = reporting_month
                st.write("PL_date_header,current_month_rows",PL_date_header,current_month_rows)
                return PL_date_header,current_month_rows,PL.iloc[current_month_rows,:]
            else:
                #st.write("valid_col_index",valid_col_index,"valid_col_mask",valid_col_mask)
                st.error("Failed to identify any month/year header in sheet: '{}', please add the month/year header and re-upload.".format(sheet_name))
                st.stop()
        elif len(valid_col_index) == 1:  #  only one column contain numeric data
            only_numeric_column_value=PL_temp.iloc[:,valid_col_index[0]]
            # count the value in numeric column
            count_non = only_numeric_column_value.isna().sum()
            # Count string values
            count_str = only_numeric_column_value.apply(lambda x: isinstance(x, str)).sum()
            # Count numeric values
            count_num = only_numeric_column_value.apply(lambda x: pd.to_numeric(x, errors='coerce')).notna().sum()

            # numeric data is supposed to be more than character data
            if (count_str>0 and (count_num/count_str)<0.7):
                st.error("Failed to identify Year/Month header for sheet: '{}', please add the month/year header and re-upload.".format(sheet_name))
                st.stop()
            else:
		# first_tenant_account_row -1 is the header row No. (used to remove the above rows, and prevent map new accounts)
                #st.write("first_tenant_account_row",first_tenant_account_row,PL.iloc[first_tenant_account_row,:])
                PL_date_header=[reporting_month if x else 0 for x in valid_col_mask]
                return PL_date_header,first_tenant_account_row-1,[]
        else:
            st.error("Failed to identify {}/{} header for sheet: '{}', please add the month/year header and re-upload.".format(int(reporting_month[4:6]),reporting_month[0:4],sheet_name))
            st.stop()

# manage entity mapping in "Manage Mapping" 
def Manage_Entity_Mapping(operator):
    global entity_mapping
    #all the properties are supposed to be in entity_mapping. 
    entity_mapping_updation=pd.DataFrame(columns=["Property_Name","Sheet_Name_Finance","Sheet_Name_Occupancy","Sheet_Name_Balance_Sheet","Column_Name"])
    number_of_property=entity_mapping.shape[0]
    with st.form(key="Mapping Properties"):
        col1,col2,col3,col4=st.columns([4,3,3,3])
        with col1:
            st.write("Property")
        with col2:
            st.write("P&L Sheetname")    
        with col3: 
            st.write("Occupancy Sheetname")    
        with col4:
            st.write("Balance sheet Sheetname")  
        i=0
        for entity in entity_mapping.index:
            col1,col2,col3,col4=st.columns([4,3,3,3])
            with col1:
                st.write("")
                st.write(entity_mapping.loc[entity,"Property_Name"])
            with col2:
                entity_mapping_updation.loc[i,"Sheet_Name_Finance"]=st.text_input("",placeholder =entity_mapping.loc[entity,"Sheet_Name_Finance"],key="P&L"+entity)    
            with col3: 
                entity_mapping_updation.loc[i,"Sheet_Name_Occupancy"]=st.text_input("",placeholder =entity_mapping.loc[entity,"Sheet_Name_Occupancy"],key="Census"+entity)     
            with col4:
                entity_mapping_updation.loc[i,"Sheet_Name_Balance_Sheet"]=st.text_input("",placeholder =entity_mapping.loc[entity,"Sheet_Name_Balance_Sheet"],key="BS"+entity) 
            i+=1 
        submitted = st.form_submit_button("Submit")
            
    if submitted:
        i=0
        for entity in entity_mapping.index:
            if entity_mapping_updation.loc[i,"Sheet_Name_Finance"]:
                entity_mapping.loc[entity,"Sheet_Name_Finance"]=entity_mapping_updation.loc[i,"Sheet_Name_Finance"] 
            if entity_mapping_updation.loc[i,"Sheet_Name_Occupancy"]:
                entity_mapping.loc[entity,"Sheet_Name_Occupancy"]=entity_mapping_updation.loc[i,"Sheet_Name_Occupancy"]
            if  entity_mapping_updation.loc[i,"Sheet_Name_Balance_Sheet"]:
                entity_mapping.loc[entity,"Sheet_Name_Balance_Sheet"]=entity_mapping_updation.loc[i,"Sheet_Name_Balance_Sheet"] 
            i+=1

        download_report(entity_mapping[["Property_Name","Sheet_Name_Finance","Sheet_Name_Occupancy","Sheet_Name_Balance_Sheet"]],"Properties Mapping_{}".format(operator))
        # update entity_mapping in Onedrive    
        Update_File_Onedrive(mapping_path,entity_mapping_filename,entity_mapping,operator,None,entity_mapping_str_col)
        return entity_mapping

# no cache 
def Manage_Account_Mapping(new_tenant_account_list,sheet_name="False"):
    global account_mapping
    st.warning("Please complete mapping for below new account:")
    i=0
    count=len(new_tenant_account_list)
    Sabra_main_account_list=[np.nan] * count
    Sabra_second_account_list=[np.nan] * count
    Sabra_main_account_value=[np.nan] * count
    Sabra_second_account_value=[np.nan] * count
    with st.form(key=new_tenant_account_list[0]):
        for i in range(count):
            if sheet_name=="False":
                st.markdown("## Map **'{}'** to Sabra account".format(new_tenant_account_list[i])) 
            else:
                st.markdown("## Map **'{}'** in '{}' to Sabra account".format(new_tenant_account_list[i],sheet_name)) 
            col1,col2=st.columns(2) 
            with col1:
                st.write("Sabra main account")
                Sabra_main_account_list[i]=streamlit_tree_select.tree_select(parent_hierarchy_main,only_leaf_checkboxes=True,key=str(new_tenant_account_list[i])) 
            with col2:
                st.write("Sabra second account")
                Sabra_second_account_list[i]= streamlit_tree_select.tree_select(parent_hierarchy_second,only_leaf_checkboxes=True,key=str(new_tenant_account_list[i])+"1")
        submitted = st.form_submit_button("Submit")    

        if submitted:
            for i in range(count):
                if len(Sabra_main_account_list[i]['checked'])==1:
                    Sabra_main_account_value[i]=Sabra_main_account_list[i]['checked'][0].upper()          
                elif len(Sabra_main_account_list[i]['checked'])>1:
                    if len(Sabra_main_account_list[i]['checked'])==2 and Sabra_main_account_list[i]['checked'][0]=="Management Fee":
                        Sabra_main_account_value[i]="T_MGMT_FEE"  
                    else:
                        st.warning("Only one to one mapping is allowed, but {} has more than one mappings.".format(new_tenant_account_list[i]))
                        st.stop()
                elif Sabra_main_account_list[i]['checked']==[] and Sabra_second_account_list[i]['checked']==[]:
                    st.warning("Please select Sabra account for '{}'".format(new_tenant_account_list[i]))
                    st.stop()
                elif Sabra_main_account_list[i]['checked']==[]:
                    Sabra_main_account_value[i]=''
            
                if Sabra_second_account_list[i]['checked']==[]:
                    Sabra_second_account_value[i]=''
                elif len(Sabra_second_account_list[i]['checked'])==1:
                    Sabra_second_account_value[i]=Sabra_second_account_list[i]['checked'][0].upper()
                elif len(Sabra_second_account_list[i]['checked'])>1:
                    st.warning("Only one to one mapping is allowed, but {} has more than one mappings.".format(new_tenant_account_list[i]))
                    st.stop()
	
        else:
            st.stop()
                
        #insert new record to the bottom line of account_mapping
        new_accounts_df = pd.DataFrame({'Sabra_Account': Sabra_main_account_value, 'Sabra_Second_Account': Sabra_second_account_value, 'Tenant_Account': new_tenant_account_list,'Tenant_Formated_Account':list(map(lambda x:x.upper().strip(), new_tenant_account_list))})
        new_accounts_df["Operator"]=operator
	
        #new_mapping_row=[operator,Sabra_main_account_value,Sabra_second_account_value,new_tenant_account_list[0],new_tenant_account_list[0].upper(),"N"]            
        account_mapping=pd.concat([account_mapping, new_accounts_df],ignore_index=True)
        Update_File_Onedrive(mapping_path,account_mapping_filename,account_mapping,operator,None,account_mapping_str_col)
        st.success("New accounts mapping were successfully saved.")    
    return account_mapping


@st.cache_data 
def Map_PL_Sabra(PL,entity):
    # remove no need to map from account_mapping
    main_account_mapping=account_mapping.loc[list(map(lambda x:x==x and x.upper()!='NO NEED TO MAP',account_mapping["Sabra_Account"])),:]

    #concat main accounts with second accounts	
    second_account_mapping=account_mapping.loc[(account_mapping["Sabra_Second_Account"]==account_mapping["Sabra_Second_Account"])&(account_mapping["Sabra_Second_Account"]!="NO NEED TO MAP")& (pd.notna(account_mapping["Sabra_Second_Account"]))][["Sabra_Second_Account","Tenant_Formated_Account","Tenant_Account","Conversion"]].\
                           rename(columns={"Sabra_Second_Account": "Sabra_Account"})
    second_account_mapping=second_account_mapping.dropna(subset="Sabra_Account")
    second_account_mapping=second_account_mapping[second_account_mapping["Sabra_Account"]!=" "]
    PL.index.name="Tenant_Account"
    PL["Tenant_Formated_Account"]=list(map(lambda x:x.upper() if isinstance(x, str) else x,PL.index))
    PL=pd.concat([PL.merge(second_account_mapping,on="Tenant_Formated_Account",how='right'),PL.merge(main_account_mapping[main_account_mapping["Sabra_Account"]==main_account_mapping["Sabra_Account"]]\
                                            [["Sabra_Account","Tenant_Formated_Account","Tenant_Account","Conversion"]],on="Tenant_Formated_Account",how='right')])
    # remove blank sabra_account (corresponds to "no need to map")	
    PL=PL[PL['Sabra_Account']!=" "]
    PL.dropna(subset=['Sabra_Account'], inplace=True)
    PL=PL.reset_index(drop=True)

    
    if isinstance(entity, str):# one entity,  properties are in separate sheet
        month_cols=list(filter(lambda x:str(x[0:2])=="20",PL.columns))
        for i in range(len(PL.index)):
            conversion=PL.loc[i,"Conversion"]
            if conversion!=conversion or pd.isna(conversion):
                continue
            else:
                for month in month_cols:
                    before_conversion=PL.loc[i,month]
                    if before_conversion!=before_conversion:
                        continue 
                    elif conversion=="/monthdays":	
                        PL.loc[i,month]=before_conversion/monthrange(int(str(month)[0:4]), int(str(month)[4:6]))[1]
                    elif conversion=="*monthdays":
                        PL.loc[i,month]= before_conversion*monthrange(int(str(month)[0:4]), int(str(month)[4:6]))[1]
                    elif conversion[0]=="*":
                        PL.loc[i,month]= before_conversion*float(conversion.split("*")[1])
        PL=PL.drop(["Tenant_Formated_Account","Conversion","Tenant_Account"], axis=1)
        PL["ENTITY"]=entity	    
         
    elif isinstance(entity, list):  # multiple properties are in one sheet,column name of data is "value" 
        monthdays=monthrange(int(str(reporting_month)[0:4]), int(str(reporting_month)[4:6]))[1]
        for i in range(len(PL.index)):
            conversion=PL.loc[i,"Conversion"]
            if conversion!=conversion or pd.isna(conversion):
                continue
            else:
                for entity_j in entity:
                    before_conversion=PL.loc[i,entity_j]
                    if before_conversion!=before_conversion or pd.isna(before_conversion):
                        continue 
                    elif conversion=="/monthdays":	
                        PL.loc[i,entity_j]=before_conversion/monthdays
                    elif conversion=="*monthdays":
                        PL.loc[i,entity_j]= before_conversion*monthdays
                    elif conversion[0]=="*":
                        PL.loc[i,entity_j]= before_conversion*float(conversion.split("*")[1])
        #property_header = [x for x in PL.columns if x not in ["Sabra_Account","Tenant_Account"]]
        PL=PL.drop(["Tenant_Formated_Account","Conversion"], axis=1)
        PL = pd.melt(PL, id_vars=['Sabra_Account','Tenant_Account'], value_vars=entity, var_name='ENTITY')     
        PL=PL.drop(["Tenant_Account"], axis=1)
    #PL_with_detail=copy.copy(PL)
    #PL_with_detail=PL_with_detail.set_index(['ENTITY', 'Sabra_Account',"Tenant_Account"])

    # group by Sabra_Account
    PL = PL.groupby(by=['ENTITY',"Sabra_Account"], as_index=True).sum()
    PL= PL.apply(Format_Value)    # do these two step, so Total_PL can use combine.first
    #return PL,PL_with_detail   
    return PL   


	
@st.cache_data
def Compare_PL_Sabra(Total_PL,reporting_month):
#def Compare_PL_Sabra(Total_PL,PL_with_detail,reporting_month):
    #PL_with_detail=PL_with_detail.reset_index(drop=False)
    diff_BPC_PL=pd.DataFrame(columns=["TIME","ENTITY","Sabra_Account","Sabra","P&L","Diff (Sabra-P&L)","Diff_Percent"])
    #diff_BPC_PL_detail=pd.DataFrame(columns=["ENTITY","Sabra_Account","Tenant_Account","Month","Sabra","P&L Value","Diff (Sabra-P&L)",""])
    month_list = list(filter(lambda x:x!=reporting_month, Total_PL.columns))
   
    for entity in entity_mapping.index:
        for timeid in month_list: 
            if entity not in Total_PL.index.get_level_values('ENTITY'):
                break	
	    # if this entity don't have data for this timeid(new/transferred property), skip to next month
            elif Total_PL.loc[entity][timeid].apply(pd.isna).all():
                break
            for matrix in BPC_Account.loc[(BPC_Account["Category"]!="Balance Sheet")]["BPC_Account_Name"]: 
            #for matrix in BPC_Account["BPC_Account_Name"]: 
                try:
                    BPC_value=int(BPC_pull.loc[entity,matrix][timeid])
                except:
                    BPC_value=0
                try:
                    PL_value=int(Total_PL.loc[entity,matrix][timeid])
                except:
                    PL_value=0
                if BPC_value==0 and PL_value==0:
                    continue
                diff=BPC_value-PL_value
                diff_percent=abs(diff)/max(abs(PL_value),abs(BPC_value))
                if diff_percent>=0.001: 
                    # for diff_BPC_PL			
                    diff_single_record=pd.DataFrame({"TIME":timeid,"ENTITY":entity,"Sabra_Account":matrix,"Sabra":BPC_value,\
                                                     "P&L":PL_value,"Diff (Sabra-P&L)":diff,"Diff_Percent":diff_percent},index=[0])


                    
		    # for diff_detail_records
                    #diff_detail_records=PL_with_detail.loc[(PL_with_detail["Sabra_Account"]==matrix)&(PL_with_detail["ENTITY"]==entity)]\
			                #[["ENTITY","Sabra_Account","Tenant_Account",timeid]].rename(columns={timeid:"P&L Value"})
                    #if there is no record in diff_detail_records, means there is no mapping
                    #if diff_detail_records.shape[0]==0:
                        #diff_detail_records=pd.DataFrame({"ENTITY":entity,"Sabra_Account":matrix,"Tenant_Account":"Miss mapping accounts","Month":timeid,"Sabra":BPC_value,"P&L Value":0,"Diff (Sabra-P&L)":diff},index=[0]) 
                    #else:
                        #diff_detail_records["Month"]=timeid
                        #diff_detail_records["Sabra"]=BPC_value
                        #diff_detail_records["Diff (Sabra-P&L)"]=diff

                    if diff_BPC_PL.isna().shape[0]==0:
                        diff_BPC_PL = diff_single_record
                        #diff_BPC_PL_detail=diff_detail_records
                    else:
                        diff_BPC_PL=pd.concat([diff_BPC_PL,diff_single_record],ignore_index=True)
                        #diff_BPC_PL_detail=pd.concat([diff_BPC_PL_detail,diff_detail_records],ignore_index=True)
			    
                    
    if diff_BPC_PL.shape[0]>0:
        #percent_discrepancy_accounts=diff_BPC_PL.shape[0]/(BPC_Account.shape[0]*len(Total_PL.columns))
        diff_BPC_PL=diff_BPC_PL.merge(BPC_Account[["Category","Sabra_Account_Full_Name","BPC_Account_Name"]],left_on="Sabra_Account",right_on="BPC_Account_Name",how="left")        
        diff_BPC_PL=diff_BPC_PL.merge(entity_mapping.reset_index(drop=False)[["ENTITY","Property_Name"]], on="ENTITY",how="left")
    return diff_BPC_PL
    #return diff_BPC_PL,diff_BPC_PL_detail
	
def color_missing(data):
    return f'background-color: rgb(255, 204, 204);'

def View_Summary():
    global Total_PL,reporting_month_data,reporting_month
    def highlight_total(df):
        return ['color: blue']*len(df) if df.Sabra_Account.startswith("Total - ") else ''*len(df)
    Total_PL = Total_PL.fillna(0).infer_objects(copy=False)

    reporting_month_data=Total_PL[reporting_month].reset_index(drop=False)
    reporting_month_data=reporting_month_data.merge(BPC_Account, left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")	
    reporting_month_data=reporting_month_data.merge(entity_mapping[["Property_Name"]], on="ENTITY",how="left")
    # check patient days ( available days > patient days)	
    check_patient_days=reporting_month_data[(reporting_month_data["Sabra_Account"].isin(availble_unit_accounts)) | (reporting_month_data["Category"]=='Patient Days')]
    check_patient_days.loc[check_patient_days['Category'] == 'Facility Information', 'Category'] = 'Operating Beds'
    check_patient_days=check_patient_days[["Property_Name","Category",reporting_month]].groupby(["Property_Name","Category"]).sum()
    check_patient_days = check_patient_days.fillna(0).infer_objects(copy=False)
    #check if available unit changed by previous month
    Check_Available_Units(check_patient_days,reporting_month)
	
    
    #check missing category ( example: total revenue= 0, total Opex=0...)	
    category_list=['Revenue','Patient Days','Operating Expenses',"Facility Information","Balance Sheet"]
    entity_list=list(reporting_month_data["ENTITY"].unique())
    current_cagegory=reporting_month_data[["Property_Name","Category","ENTITY",reporting_month]][reporting_month_data["Category"].\
	    isin(category_list)].groupby(["Property_Name","Category","ENTITY"]).sum().reset_index(drop=False)
    full_category = pd.DataFrame(list(product(entity_list,category_list)), columns=['ENTITY', 'Category'])
    missing_category=full_category.merge(current_cagegory,on=['ENTITY', 'Category'],how="left")
    missing_category=missing_category[(missing_category[reporting_month]==0)|(missing_category[reporting_month].isnull())]
    missing_category[reporting_month]="NA" 


    #if "Facility Information" in list(missing_category["Category"]):
        # fill the facility info with historical data
        #Check_Available_Beds(missing_category,reporting_month)
        #missing_category=missing_category[missing_category["Category"]!="Facility Information"]

    if missing_category.shape[0]>0:
        st.write("No data detected for below properties and accounts: ")
        missing_category=missing_category[["ENTITY",reporting_month,"Category"]].merge(entity_mapping[["Property_Name"]], on="ENTITY",how="left")
        st.dataframe(missing_category[["Property_Name","Category",reporting_month]].style.map(color_missing, subset=[reporting_month]),
		    column_config={
			        "Property_Name": "Property",
			        "Category":"Account category",
		                 reporting_month:reporting_month[4:6]+"/"+reporting_month[0:4]},
			    hide_index=True)
	     

    #duplicates = reporting_month_data[reporting_month_data.duplicated(subset=["Sabra_Account_Full_Name", "Category"], keep=False)]

    reporting_month_data =reporting_month_data.pivot_table(index=["Sabra_Account_Full_Name","Category"], columns="Property_Name", values=reporting_month,aggfunc='last')
    reporting_month_data.reset_index(drop=False,inplace=True)

    reporting_month_data.rename(columns={"Sabra_Account_Full_Name":"Sabra_Account"},inplace=True) 
    reporting_month_data=reporting_month_data.dropna(subset=["Sabra_Account"])
    sorter=["Facility Information","Patient Days","Revenue","Operating Expenses","Non-Operating Expenses","Labor Expenses","Management Fee","Balance Sheet","Additional Statistical Information","Government Funds"]
    sorter=list(filter(lambda x:x in reporting_month_data["Category"].unique(),sorter))
    reporting_month_data.Category = reporting_month_data.Category.astype("category")
    reporting_month_data.Category = reporting_month_data.Category.cat.set_categories(sorter)
    reporting_month_data=reporting_month_data.sort_values(["Category"]) 
    reporting_month_data = pd.concat([reporting_month_data.groupby(by='Category', as_index=False,observed=False).sum().assign(Sabra_Account="Total_Sabra"), reporting_month_data]).sort_values(by='Category', kind='stable', ignore_index=True)[reporting_month_data.columns]
    set_empty=list(reporting_month_data.columns)
    set_empty.remove("Category")
    set_empty.remove("Sabra_Account")
    for i in range(reporting_month_data.shape[0]):
        if reporting_month_data.loc[i,"Sabra_Account"]=="Total_Sabra":
            reporting_month_data.loc[i,"Sabra_Account"]="Total - "+reporting_month_data.loc[i,'Category']
            if reporting_month_data.loc[i,'Category'] in ["Facility Information","Additional Statistical Information","Balance Sheet"]:                
                reporting_month_data.loc[i,set_empty]=np.nan

    entity_columns=reporting_month_data.drop(["Sabra_Account","Category"],axis=1).columns	
    if len(reporting_month_data.columns)>3:  # if there are more than one property, add total column
        reporting_month_data["Total"] = reporting_month_data[entity_columns].sum(axis=1)
        reporting_month_data=reporting_month_data[["Sabra_Account","Total"]+list(entity_columns)]
    else:
        reporting_month_data=reporting_month_data[["Sabra_Account"]+list(entity_columns)]   

    with st.expander("Summary of {}/{} reporting".format(reporting_month[4:6],reporting_month[0:4]) ,expanded=True):
        ChangeWidgetFontSize("Summary of {}/{} reporting".format(reporting_month[4:6],reporting_month[0:4]), '25px')
        download_report(reporting_month_data,"{} {}-{} Report".format(operator,reporting_month[4:6],reporting_month[0:4]))
        reporting_month_data=reporting_month_data.apply(Format_Value)
        reporting_month_data=reporting_month_data.fillna(0).infer_objects(copy=False)
        reporting_month_data=reporting_month_data.replace(0,'')
        styled_table = (reporting_month_data.style.set_table_styles(styles).apply(highlight_total, axis=1).format(precision=0, thousands=",").hide(axis="index").to_html(escape=False)) # Use escape=False to allow HTML tags
        # Display the HTML using st.markdown
        st.markdown(styled_table, unsafe_allow_html=True)
        st.write("")
        
# no cache
def Submit_Upload_Latestmonth():
    global Total_PL,reporting_month   
    upload_reporting_month=Total_PL[reporting_month].reset_index(drop=False)
    upload_reporting_month["TIME"]=reporting_month
    upload_reporting_month=upload_reporting_month.rename(columns={reporting_month:"Amount"})
    current_time = datetime.now(pytz.timezone('America/Los_Angeles')).strftime("%H:%M")
    upload_reporting_month["Latest_Upload_Time"]=str(today)+" "+current_time
    upload_reporting_month["Operator"]=operator
    upload_reporting_month=upload_reporting_month.apply(Format_Value)

    if not st.session_state.clicked["submit_report"]:
        st.stop()
    else:
         # save reporting month data to OneDrive
        if Update_File_Onedrive(master_template_path,monthly_reporting_filename,upload_reporting_month,operator,None,None):
            st.success("{} {} reporting data was uploaded to Sabra system successfully!".format(operator,reporting_month[4:6]+"/"+reporting_month[0:4]))
            
        else: 
            st.write(" ")  #----------record into error report------------------------	
         # save discrepancy data to OneDrive
        if len(Total_PL.columns)>1 and diff_BPC_PL.shape[0]>0:
            download_report(diff_BPC_PL[["Property_Name","TIME","Category","Sabra_Account_Full_Name","Sabra","P&L","Diff (Sabra-P&L)"]],"discrepancy")
            Update_File_Onedrive(master_template_path,discrepancy_filename,diff_BPC_PL,operator,None,None)
        
	# save original tenant P&L to OneDrive
        if not Upload_to_Onedrive(uploaded_finance,"{}/{}".format(PL_path,operator),"{}_P&L_{}-{}.xlsx".format(operator,reporting_month[4:6],reporting_month[0:4])):
            st.write("unsuccess ")  #----------record into error report------------------------	

        if BS_separate_excel=="Y":
            # save tenant BS to OneDrive
            if not Upload_to_Onedrive(uploaded_BS,"{}/{}".format(PL_path,operator),"{}_BS_{}-{}.xlsx".format(operator,reporting_month[4:6],reporting_month[0:4])):
                st.write(" unsuccess")  #----------record into error report------------------------	


# create EPM formula for download data
def EPM_Formula(data,value_name): # make sure there is no col on index for data
    data["EPM_Formula"]=""
    data["Upload_Check"]=""
    col_size=data.shape[1]
    row_size=data.shape[0]
    col_name_list=list(data.columns)
    time_col_letter=colnum_letter(col_name_list.index("TIME"))
    entity_col_letter=colnum_letter(col_name_list.index("ENTITY"))
    account_col_letter=colnum_letter(col_name_list.index("Sabra_Account"))
    facility_col_letter=colnum_letter(col_name_list.index("FACILITY_TYPE"))
    state_col_letter=colnum_letter(col_name_list.index("GEOGRAPHY"))
    leasename_col_letter=colnum_letter(col_name_list.index("LEASE_NAME"))
    inv_col_letter=colnum_letter(col_name_list.index("INV_TYPE"))
    data_col_letter=colnum_letter(col_name_list.index(value_name))    
    EPM_Formula_col_letter=colnum_letter(col_name_list.index("EPM_Formula"))
    upload_Check_col_letter=colnum_letter(col_name_list.index("Upload_Check"))
    for r in range(2,row_size+2):
        upload_formula="""=@EPMSaveData({}{},"finance",{}{},{}{},{}{},{}{},{}{},{}{},{}{},"D_INPUT","F_NONE","USD","PERIODIC","ACTUAL")""".\
		    format(data_col_letter,r,time_col_letter,r,entity_col_letter,r,account_col_letter,r,facility_col_letter,r,state_col_letter,r,leasename_col_letter,r,inv_col_letter,r)
        data.loc[r-2,"EPM_Formula"]=upload_formula
        upload_check_formula="={}{}={}{}".format(EPM_Formula_col_letter,r,data_col_letter,r)
        data.loc[r-2,"Upload_Check"]=upload_check_formula
    data["""="Consistence check:"&AND({}2:{}{})""".format(upload_Check_col_letter,upload_Check_col_letter,row_size+1)]=""
    return data
            
	
def Check_Sheet_Name_List(uploaded_file,sheet_type):
    global entity_mapping,PL_sheet_list

    try:
        PL_sheet_list = load_workbook(uploaded_file, data_only=True).sheetnames
    except TypeError as e:
        # Check if the specific TypeError message matches
        error_message = str(e)
        if "<class 'openpyxl.styles.named_styles._NamedCellStyle'>.name should be <class 'str'> but value is <class 'NoneType'>" in error_message:
            st.write("Error: The Excel file is corrupted or has invalid styles. Please open the file and re-save it, which sometimes resolves such issues.")
        else:
            st.write(f"Error: {e}")
    except Exception as e:
        st.write(f"An error occurred: {e}")

    if sheet_type=="Finance":
        missing_PL_sheet_property = entity_mapping[(~entity_mapping["Sheet_Name_Finance"].isin(PL_sheet_list))|(pd.isna(entity_mapping["Sheet_Name_Finance"]))]
        missing_PL_sheet_property_Y=missing_PL_sheet_property.loc[missing_PL_sheet_property["Finance_in_separate_sheets"]=="Y",:]
        missing_PL_sheet_property_N=missing_PL_sheet_property.loc[missing_PL_sheet_property["Finance_in_separate_sheets"]=="N",:]
        missing_occ_sheet_property = entity_mapping[(entity_mapping["Sheet_Name_Occupancy"].isin(PL_sheet_list)==False) & (~pd.isna(entity_mapping["Sheet_Name_Occupancy"]))& (entity_mapping["Sheet_Name_Finance"] != entity_mapping["Sheet_Name_Occupancy"])]
        missing_occ_sheet_property_Y=missing_occ_sheet_property.loc[missing_occ_sheet_property["Finance_in_separate_sheets"]=="Y",:]
        missing_occ_sheet_property_N=missing_occ_sheet_property.loc[missing_occ_sheet_property["Finance_in_separate_sheets"]=="N",:]
        missing_BS_sheet_property = entity_mapping[(entity_mapping["BS_separate_excel"]=="N") &(~pd.isna(entity_mapping["Sheet_Name_Balance_Sheet"]))& (entity_mapping["Sheet_Name_Finance"] != entity_mapping["Sheet_Name_Balance_Sheet"])&(entity_mapping["Sheet_Name_Balance_Sheet"].isin(PL_sheet_list)==False)]		
        missing_BS_sheet_property_Y=missing_BS_sheet_property.loc[missing_BS_sheet_property["Finance_in_separate_sheets"]=="Y",:]
        missing_BS_sheet_property_N=missing_BS_sheet_property.loc[missing_BS_sheet_property["Finance_in_separate_sheets"]=="N",:]    
        total_missing_Y=missing_PL_sheet_property_Y.shape[0]+missing_occ_sheet_property_Y.shape[0]+missing_BS_sheet_property_Y.shape[0]
        total_missing_N=missing_PL_sheet_property_N.shape[0]+missing_occ_sheet_property_N.shape[0]+missing_BS_sheet_property_N.shape[0]
    elif sheet_type=="BS": # BS in another excel file
        missing_BS_sheet_property = entity_mapping[(entity_mapping["BS_separate_excel"]=="Y") & (entity_mapping["Sheet_Name_Balance_Sheet"].isin(PL_sheet_list)==False)&(~pd.isna(entity_mapping["Sheet_Name_Balance_Sheet"]))]
        missing_BS_sheet_property_Y=missing_BS_sheet_property.loc[missing_BS_sheet_property["Finance_in_separate_sheets"]=="Y",:]
        missing_BS_sheet_property_N=missing_BS_sheet_property.loc[missing_BS_sheet_property["Finance_in_separate_sheets"]=="N",:]  
        total_missing_Y=missing_BS_sheet_property_Y.shape[0]
        total_missing_N=missing_BS_sheet_property_N.shape[0]

    if total_missing_Y+total_missing_N==0:        
        return entity_mapping
    
    if  total_missing_Y>0:
        with st.form(key=sheet_type+"_Y"):
            if sheet_type=="Finance":
                if missing_PL_sheet_property_Y.shape[0]>0:
                    for entity_i in missing_PL_sheet_property_Y.index:
                        st.warning("Please provide P&L sheet name for {}".format(entity_mapping.loc[entity_i,"Property_Name"]))
                        missing_PL_sheet_property_Y.loc[entity_i,"Sheet_Name_Finance"]=st.selectbox("Original P&L sheet name: {}".format(entity_mapping.loc[entity_i,"Sheet_Name_Finance"]),[""]+PL_sheet_list,key=entity_i+"PL_Y")
                if missing_occ_sheet_property_Y.shape[0]>0:
                    for entity_i in missing_occ_sheet_property_Y.index:
                        st.warning("Please provide Census sheet name for {}".format(entity_mapping.loc[entity_i,"Property_Name"]))
                        missing_occ_sheet_property_Y.loc[entity_i,"Sheet_Name_Occupancy"]=st.selectbox("Original Census sheet name: {}".format(entity_mapping.loc[entity_i,"Sheet_Name_Occupancy"]),[""]+PL_sheet_list,key=entity_i+"occ_Y")
            
            if missing_BS_sheet_property_Y.shape[0]>0:
                for entity_i in missing_BS_sheet_property_Y.index:
                    st.warning("Please provide Balance Sheet sheet name for {}".format(entity_mapping.loc[entity_i,"Property_Name"]))
                    missing_BS_sheet_property_Y.loc[entity_i,"Sheet_Name_Balance_Sheet"]=st.selectbox("Original 'Balance Sheet' sheet name: {}".format(entity_mapping.loc[entity_i,"Sheet_Name_Balance_Sheet"]),[""]+PL_sheet_list,key=entity_i+"bs_Y")   
            submitted = st.form_submit_button("Submit")
           
        if submitted:
            if sheet_type=="Finance":
                if (missing_PL_sheet_property_Y.shape[0]>0 and missing_PL_sheet_property_Y["Sheet_Name_Finance"].isna().any()) or (missing_occ_sheet_property_Y.shape[0]>0 and missing_occ_sheet_property_Y["Sheet_Name_Occupancy"].isna().any()) or (missing_BS_sheet_property_Y.shape[0]>0 and missing_BS_sheet_property_Y["Sheet_Name_Balance_Sheet"].isna().any()):
                    st.error("Please complete above mapping.")
                    st.stop()
                else:
                    if missing_PL_sheet_property_Y.shape[0]>0:
                        for entity_i in missing_PL_sheet_property_Y.index: 
                            entity_mapping.loc[entity_i,"Sheet_Name_Finance"]=missing_PL_sheet_property_Y.loc[entity_i,"Sheet_Name_Finance"] 
                    if missing_occ_sheet_property_Y.shape[0]>0:
                        for entity_i in missing_occ_sheet_property_Y.index:
                            entity_mapping.loc[entity_i,"Sheet_Name_Occupancy"]=missing_occ_sheet_property_Y.loc[entity_i,"Sheet_Name_Occupancy"]
                    if missing_BS_sheet_property_Y.shape[0]>0:
                        for entity_i in missing_BS_sheet_property_Y.index:
                            entity_mapping.loc[entity_i,"Sheet_Name_Balance_Sheet"]=missing_BS_sheet_property_Y.loc[entity_i,"Sheet_Name_Balance_Sheet"]
            elif sheet_type=="BS":
                if (missing_BS_sheet_property_Y.shape[0]>0 and missing_BS_sheet_property_Y["Sheet_Name_Balance_Sheet"].isna().any()):
                    st.error("Please complete Balance Sheet mapping.")
                    st.stop()
                for entity_i in missing_BS_sheet_property_Y.index:
                    entity_mapping.loc[entity_i,"Sheet_Name_Balance_Sheet"]=missing_BS_sheet_property_Y.loc[entity_i,"Sheet_Name_Balance_Sheet"]
        else:
            st.stop()
                
    elif total_missing_N>0:
        with st.form(key=sheet_type+"_N"):
            if sheet_type=="Finance":	    
                if missing_PL_sheet_property_N.shape[0]>0:
                    st.warning("Please provide P&L sheet name for properties: {}".format(",".join(list(missing_PL_sheet_property_N["Property_Name"]))))
                    PL_sheet=st.selectbox("",[""]+PL_sheet_list,key="P&L_N")
                if missing_occ_sheet_property_N.shape[0]>0:
                    st.warning("Please provide sheet name for Occupancy:")
                    occ_sheet=st.selectbox("",[""]+PL_sheet_list,key="occ_N")
            if missing_BS_sheet_property_N.shape[0]>0:
                st.warning("Please provide sheet name for Balance Sheet:")
                BS_sheet=st.selectbox("",[""]+PL_sheet_list,key="BS_N")         
            submitted = st.form_submit_button("Submit")
            if submitted:
                if sheet_type=="Finance":
                    if (missing_PL_sheet_property_N.shape[0]>0 and PL_sheet== "") or (missing_occ_sheet_property_N.shape[0]>0 and occ_sheet== "") or (missing_BS_sheet_property_N.shape[0]>0 and BS_sheet== ""):
                        st.error("Please complete above mapping.")
                        st.stop()
                    else:
                        if missing_PL_sheet_property_N.shape[0]>0:
                            entity_mapping.loc[:,"Sheet_Name_Finance"]=PL_sheet
                        if missing_occ_sheet_property_N.shape[0]>0:
                            entity_mapping.loc[:,"Sheet_Name_Occupancy"]=occ_sheet
                elif missing_BS_sheet_property_N.shape[0]>0:
                    if BS_sheet.isna():
                        st.error("Please complete Balance Sheet mapping.")
                        st.stop()
                    else:
                        entity_mapping.loc[:,"Sheet_Name_Balance_Sheet"]=BS_sheet
            else:
                st.stop()
    # update entity_mapping in onedrive  
    Update_File_Onedrive(mapping_path,entity_mapping_filename,entity_mapping,operator,None,entity_mapping_str_col)
    return entity_mapping

def View_Discrepancy_Detail():
    global diff_BPC_PL,Total_PL_detail,Total_PL ,diff_BPC_PL_detail
    # Sabra detail accounts mapping table
    def color_coding(row):
    	return ['color: blue'] * len(row) if row.Tenant_Account == " Total" else ['color: black'] * len(row)
    
    if diff_BPC_PL.shape[0]>0: 
	# format it to display
        st.markdown("---")
        st.markdown("P&L—Sabra detail accounts mapping (for discrepancy data)") 
        diff_BPC_PL_detail = (pd.concat([diff_BPC_PL_detail.groupby(["ENTITY","Sabra_Account","Month","Sabra","Diff (Sabra-P&L)"], as_index=False).sum()
                      .assign(Tenant_Account=" Total"),diff_BPC_PL_detail]).sort_values(by=["ENTITY","Sabra_Account","Month","Sabra","Diff (Sabra-P&L)"], kind='stable', ignore_index=True)[diff_BPC_PL_detail.columns])
        diff_BPC_PL_detail=diff_BPC_PL_detail.merge(BPC_Account[["BPC_Account_Name","Sabra_Account_Full_Name"]],left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")
        diff_BPC_PL_detail=diff_BPC_PL_detail.merge(entity_mapping[["Property_Name"]],left_on="ENTITY", right_on="ENTITY",how="left")
        diff_BPC_PL_detail=diff_BPC_PL_detail[["Property_Name","Month","Sabra_Account_Full_Name","Tenant_Account","Sabra","P&L Value","Diff (Sabra-P&L)"]].\
			rename(columns={"Property_Name":"Property","Sabra_Account_Full_Name":"Sabra Account"})
        diff_BPC_PL_detail=filters_widgets(diff_BPC_PL_detail,["Property","Month","Sabra Account"],"Horizontal")
        diff_BPC_PL_detail=diff_BPC_PL_detail.reset_index(drop=True)
        for i in range(diff_BPC_PL_detail.shape[0]):
            if  diff_BPC_PL_detail.loc[i,"Tenant_Account"]!=" Total":
                diff_BPC_PL_detail.loc[i,"Property"]=""
                diff_BPC_PL_detail.loc[i,"Month"]=""
                diff_BPC_PL_detail.loc[i,"Sabra Account"]=""
                diff_BPC_PL_detail.loc[i,"Sabra"]=""
                diff_BPC_PL_detail.loc[i,"Diff (Sabra-P&L)"]=""
                diff_BPC_PL_detail.loc[i,"Tenant_Account"]="—— "+diff_BPC_PL_detail.loc[i,"Tenant_Account"]
        
        st.markdown(
            """
        <style type="text/css" media="screen">
        div[role="dataframe"] ul {
            height:300px;
        }
        </style>
            """,
        unsafe_allow_html=True )
        st.markdown(diff_BPC_PL_detail.style.set_table_styles(styles).apply(color_coding, axis=1).map(left_align)
		.format(precision=0,thousands=",").hide(axis="index").to_html(),unsafe_allow_html=True)	
        st.write("")
       
         

# don't use cache
def View_Discrepancy(): 
    global diff_BPC_PL	
    if diff_BPC_PL.shape[0]>0:
        # save all the discrepancy 
        diff_BPC_PL["Operator"]=operator
        diff_BPC_PL=diff_BPC_PL.merge(entity_mapping[["GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE"]],on="ENTITY",how="left")
	# insert dims to diff_BPC_PL
        diff_BPC_PL["TIME"]=diff_BPC_PL["TIME"].apply(lambda x: "{}.{}".format(str(x)[0:4],month_abbr[int(str(x)[4:6])]))

	# only display the big discrepancy
        edited_diff_BPC_PL=diff_BPC_PL[diff_BPC_PL["Diff_Percent"]>0.15] 
        if edited_diff_BPC_PL.shape[0]>0:
            st.error("Below P&L data doesn't tie to Sabra data.  Please leave comments for discrepancy in below table.")
            edited_diff_BPC_PL.loc[:, "Type comments below"] = ""
            edited_diff_BPC_PL = st.data_editor(
	    edited_diff_BPC_PL,
	    width = 1200,
	    column_order=("Property_Name","TIME","Category","Sabra_Account_Full_Name","Sabra","P&L","Diff (Sabra-P&L)","Type comments below"),
	    hide_index=True,
	    disabled=("Property_Name","TIME","Category","Sabra_Account_Full_Name","Sabra","P&L","Diff (Sabra-P&L)"),
	    column_config={
       		"Sabra_Account_Full_Name": "Sabra_Account",
       		 "Property_Name": "Property",
		 "TIME":"Month",
		"P&L":st.column_config.TextColumn(
			"Tenant P&L",help="Tenant P&L is aggregated by detail tenant accounts connected with 'Sabra Account'"),
        	"Diff (Sabra-P&L)": st.column_config.TextColumn(
            		"Diff (Sabra-P&L)",help="Diff = Sabra-TenantP&L"),
		"Sabra": st.column_config.TextColumn(
            		"Sabra",help="Sabra data for previous month"),
		 "Type comments below":st.column_config.TextColumn(
            		"Type comments below",
            		help="Please provide an explanation and solution on discrepancy, like: confirm the changed. overwrite Sabra data with new one...",
			disabled =False,
            		required =False)
		}) 

            col1,col2=st.columns([1,6]) 
            with col1:
                submit_com=st.button("Submit comments")
            #View_Discrepancy_Detail()
            if submit_com:
                with st.empty():
                    with col2:
                        st.markdown("✔️ :green[Comments uploaded]")
                        st.write(" ")
                    # insert comments to diff_BPC_PL
                    diff_BPC_PL=pd.merge(diff_BPC_PL,edited_diff_BPC_PL[["Property_Name","TIME","Sabra_Account_Full_Name","Type comments below"]],on=["Property_Name","TIME","Sabra_Account_Full_Name"],how="left")

        else:
            st.success("All previous data in P&L ties with Sabra data")
    else:
            st.success("All previous data in P&L ties with Sabra data")


def Identify_Column_Name_Header(PL,entity_list,sheet_name):  # all properties are in one sheet
    # return the row number of property header and mapped_entity, for example: 1, ["0","0",Sxxxx,Sxxxx,"0",Sxxxx,"0"...]
    #	Column_Name and entity_list has same order
    entity_without_propertynamefinance=entity_mapping[(entity_mapping['Column_Name'].isna()) | (entity_mapping['Column_Name'].str.strip() == "")].index.tolist()
    column_name_list_in_mapping=[str(x).upper().strip() for x in entity_mapping.loc[entity_list]["Column_Name"] if pd.notna(x) and str(x).strip()]
    max_match=[]
    for row_i in range(PL.shape[0]):
        canditate_row=list(map(lambda x: str(x).upper().strip() if pd.notna(x) else x,list(PL.iloc[row_i,:])))  
        match_names = [item for item in canditate_row if item in column_name_list_in_mapping]
        if len(match_names)==len(column_name_list_in_mapping) and len(entity_without_propertynamefinance)==0: # find the property name header row, transfer them into entity id
            duplicate_check = [name for name in set(match_names) if match_names.count(name) > 1]
            if len(duplicate_check)>0:
                st.error("Detected duplicated column names—— {} in sheet '{}'. Please fix and re-upload.".format(", ".join(f"'{item}'" for item in duplicate_check),sheet_name))
                st.stop()
            else:
                mapping_dict = {column_name_list_in_mapping[i]: entity_list[i] for i in range(len(column_name_list_in_mapping))}
                mapped_entity = [mapping_dict[property] if property in mapping_dict else "0" for property in canditate_row]
                return row_i,mapped_entity
	
        elif len(match_names)>len(max_match):
            max_match=match_names
            header_row=canditate_row
            max_match_row=row_i
            if len(match_names)==len(column_name_list_in_mapping):
                break
        if len(max_match)>2:
            break
		
    if len(max_match)==0:
        st.error("Fail to identify facility column names in sheet '{}'. The previous column names are as below. Please add and re-upload.".format(sheet_name))
        st.write('    '.join(column_name_list_in_mapping))
        st.stop()
    elif len(max_match)>0: # only part of entities have property name in P&L
        duplicate_check = [name for name in set(match_names) if match_names.count(name) > 1]
        if len(duplicate_check)>0:
            st.error("Detected duplicated column names—— {} in sheet '{}'. Please fix and re-upload.".format(", ".join(f"'{item}'" for item in duplicate_check),sheet_name))
            st.stop()
        miss_match_names = [item for item in column_name_list_in_mapping  if item not in max_match]
        total_missed_entities=entity_mapping[entity_mapping["Column_Name"].str.upper().str.strip().isin(miss_match_names)].index.tolist()+entity_without_propertynamefinance
        miss_column_mapping=entity_mapping.loc[total_missed_entities]
        column_names=[str(x) for x in PL.iloc[max_match_row,:] if pd.notna(x) and str(x).upper().strip() not in column_name_list_in_mapping]
        if len(total_missed_entities)>0:
            st.error("Please map the column names for following facilities in sheet {}.".format(sheet_name))
            with st.form(key="miss_match_column_name"):
                for entity_i in total_missed_entities:
                    st.warning("Column name for facility {}".format(entity_mapping.loc[entity_i,"Property_Name"]))
                    miss_column_mapping.loc[entity_i,"Column_Name"]=st.selectbox("Original column name: {}".format(\
			entity_mapping.loc[entity_i,"Column_Name"]),[""]+column_names,key=entity_i+"miss_column")
                submitted = st.form_submit_button("Submit")
           
            if submitted:
                if (miss_column_mapping["Column_Name"] == "").any():
                    st.error("Please complete all the mapping.")
                    st.stop()
            
                for entity_i in miss_column_mapping.index: 
                    entity_mapping.loc[entity_i,"Column_Name"]=miss_column_mapping.loc[entity_i,"Column_Name"]     

                column_name_list_in_mapping=[str(x).upper().strip() for x in entity_mapping.loc[entity_list]["Column_Name"]]
                duplicate_check = [name for name in set(column_name_list_in_mapping) if column_name_list_in_mapping.count(name) > 1]

                if len(duplicate_check)>0:
                    st.error( "The following column has been mapped to more than one facility in sheet '{}'. Please fix and re-upload:".format(sheet_name))
                    st.error(", ".join(f"'{item}'" for item in duplicate_check))
                    st.stop()

                mapping_dict = {column_name_list_in_mapping[i]: entity_list[i] for i in range(len(entity_list))}
                mapped_entity = [mapping_dict[property] if property in mapping_dict else "0" for property in header_row]
                # update entity_mapping in onedrive  
                Update_File_Onedrive(mapping_path,entity_mapping_filename,entity_mapping,operator,None,entity_mapping_str_col)
        
                return row_i,mapped_entity
            else:
                st.stop()
# no cache
def Read_Clean_PL_Multiple(entity_list,sheet_type,uploaded_file,account_pool,sheet_name):  
    global account_mapping,reporting_month
    #check if sheet names in list are same, otherwise, ask user to select correct sheet name.
    if sheet_type=="Sheet_Name_Finance":  
        sheet_type_name="P&L"
    elif sheet_type=="Sheet_Name_Occupancy":
        sheet_type_name="Occupancy"
    elif sheet_type=="Sheet_Name_Balance_Sheet":
        sheet_type_name="Balance Sheet"

    # read data from uploaded file
    PL = pd.read_excel(uploaded_file,sheet_name=sheet_name,header=None)
	
    # Start checking process
    if True:   
        tenantAccount_col_no=Identify_Tenant_Account_Col(PL,sheet_name,sheet_type_name,account_pool,tenant_account_col)
        if tenantAccount_col_no==None:
            st.error("Fail to identify tenant account column in sheet '{}'".format(sheet_name))
            st.stop()    

        entity_header_row_number,new_entity_header=Identify_Column_Name_Header(PL,entity_list,sheet_name) 
	#set tenant_account as index of PL
        PL=PL.set_index(PL.iloc[:,tenantAccount_col_no].values)	
  
	#remove row above property header
        PL=PL.iloc[entity_header_row_number+1:,:]

        # remove column without column name, (value in property header that equal to 0)
        non_zero_columns = [val !="0" for val in new_entity_header]
        PL = PL.loc[:,non_zero_columns]    
        PL.columns= [value for value in new_entity_header if value != "0"]
	    
        #remove rows without tenant account
        nan_index=list(filter(lambda x: pd.isna(x) or x=="" or x==" " or x!=x or x=="nan",PL.index))
        PL.drop(nan_index, inplace=True)
        #set index as str ,strip
        PL.index=map(lambda x:str(x).strip(),PL.index)
        PL=PL.map(lambda x: 0 if x!=x or pd.isna(x) or isinstance(x, str) or x==" " else x)	    
        # don't removes with all nan/0, because some property may have no data and need to keep empty
        #PL=PL.loc[:,(PL!= 0).any(axis=0)]
        # remove rows with all nan/0 value
        #PL=PL.loc[(PL!= 0).any(axis=1),:]
        PL = PL.loc[~PL.apply(lambda x: x.isna().all() or (x.fillna(0) == 0).all(), axis=1)]
        # mapping new tenant accounts
        new_tenant_account_list=list(filter(lambda x: str(x).upper().strip() not in list(account_mapping["Tenant_Formated_Account"]),PL.index))
        # remove duplicate new account
        new_tenant_account_list=list(set(new_tenant_account_list))    
        if len(new_tenant_account_list)>0:
            account_mapping=Manage_Account_Mapping(new_tenant_account_list,sheet_name)
		
        #if there are duplicated accounts in P&L, ask for confirming
        dup_tenant_account_total=list(set([x for x in PL.index if list(PL.index).count(x) > 1]))
        if len(dup_tenant_account_total)>0:
            dup_tenant_account=[x for x in dup_tenant_account_total if x.upper() not in list(account_mapping[account_mapping["Sabra_Account"]=="NO NEED TO MAP"]["Tenant_Formated_Account"])]
         
            for idx_account in dup_tenant_account[:]:
		# Extract records with current index value
                records_idx = PL.loc[idx_account]
                # if all records have the same data, remove the duplicated records, remove this account from dup_tenant_account
                if (records_idx == records_idx.iloc[0]).all(axis=None):
                    PL = pd.concat([PL.loc[idx_account].drop_duplicates().head(1), PL.loc[PL.index != idx_account]])
                    dup_tenant_account.remove(idx_account)  
            if len(dup_tenant_account)>0:
                st.error("Duplicated accounts detected in {} sheet '{}'. Please rectify them to avoid repeated calculations: **{}** ".format(sheet_type_name,sheet_name,", ".join(dup_tenant_account)))
	    
        # Map PL accounts and Sabra account
        #PL,PL_with_detail=Map_PL_Sabra(PL,entity_list) 
	# map sabra account with tenant account, groupby sabra account
        PL=Map_PL_Sabra(PL,entity_list) # index are ('ENTITY',"Sabra_Account")
        PL.rename(columns={"value":reporting_month},inplace=True)
        #PL_with_detail.rename(columns={"values":reporting_month},inplace=True)
    #return PL,PL_with_detail
    return PL
	
@st.cache_data
def Get_Previous_Months(reporting_month,full_date_header):
    # Convert the reporting_month string to a datetime object
    latest_date = datetime.strptime(reporting_month, "%Y%m")
    month_list = [reporting_month]
    for i in range(previous_monthes_comparison):
        # Subtract i months to get the previous month
        previous_date = latest_date - timedelta(days=latest_date.day, weeks=i*4)
        # Format the date back to the desired string format and append to the list
        month_list.append(previous_date.strftime("%Y%m"))
    month_select=list(filter(lambda x: x in month_list,full_date_header))	
    return month_select

#no cache    
def Read_Clean_PL_Single(entity_i,sheet_type,uploaded_file,account_pool):  
    global account_mapping,reporting_month,tenant_account_col,date_header
    sheet_name=str(entity_mapping.loc[entity_i,sheet_type])
    property_name= str(entity_mapping.loc[entity_i,"Property_Name"] ) 

    if sheet_type=="Sheet_Name_Finance":  
        sheet_type_name="P&L"
    elif sheet_type=="Sheet_Name_Occupancy":
        sheet_type_name="Occupancy"
    elif sheet_type=="Sheet_Name_Balance_Sheet":
        sheet_type_name="Balance"

    # read data from uploaded file
    PL = pd.read_excel(uploaded_file,sheet_name=sheet_name,header=None)	
    # Start checking process
    with st.spinner("********Start to check facility—'"+property_name+"' in sheet '"+sheet_name+"'********"):
        tenantAccount_col_no=Identify_Tenant_Account_Col(PL,sheet_name,sheet_type_name,account_pool,tenant_account_col)
        if tenantAccount_col_no==None:
            st.error("Fail to identify tenant account column in {} sheet '{}'".format(sheet_type_name,sheet_name))
            st.stop()   
        else:
            tenant_account_col=tenantAccount_col_no
		
        #set tenant_account as index of PL
        PL = PL.set_index(PL.columns[tenantAccount_col_no], drop=False)
        date_header=Identify_Month_Row(PL,sheet_name,date_header,tenantAccount_col_no)
        if all(x=="0" or x==0 for x in date_header[0]):
            st.error("Fail to identify Month/Year header in {} sheet '{}', please add it and re-upload.".format(sheet_type_name,sheet_name))
            st.stop()  
		
        # select only two or one previous months for columns
        month_select = Get_Previous_Months(reporting_month,date_header[0]) 
        
 
        #remove row above date, to prevent to map these value as new accounts
        PL=PL.iloc[date_header[1]+1:,:]
	#remove rows with nan tenant account
        nan_index=list(filter(lambda x:pd.isna(x) or x=="nan" or x=="" or x==" " or x!=x or x==0 ,PL.index))
        PL.drop(nan_index, inplace=True)
        #set index as str ,strip,upper
        PL.index=map(lambda x:str(x).strip().upper(),PL.index)
	    
        # filter columns with month_select
        selected_columns = [val in month_select for val in date_header[0]]
        PL = PL.loc[:,selected_columns]   
        PL.columns= [value for value in date_header[0] if value in month_select]        
           
        # remove columns with all nan/0 or a combination of nan and 0
        #PL=PL.loc[:,(PL!= 0).any(axis=0)]
        # remove rows with all nan/0 value or a combination of nan and 0
        PL = PL.loc[~PL.apply(lambda x: x.isna().all() or (x.fillna(0) == 0).all(), axis=1)]
	# mapping new tenant accounts
        new_tenant_account_list=list(filter(lambda x: x not in list(account_mapping["Tenant_Formated_Account"]),PL.index))
        new_tenant_account_list=list(set(new_tenant_account_list))    
        if len(new_tenant_account_list)>0:
            account_mapping=Manage_Account_Mapping(new_tenant_account_list,sheet_name)        
     
        #if there are duplicated accounts in P&L, ask for confirming
        dup_tenant_account_total=set([x for x in PL.index if list(PL.index).count(x) > 1])

        if len(dup_tenant_account_total)>0:
            dup_tenant_account=[x for x in dup_tenant_account_total if x.upper() not in list(account_mapping[account_mapping["Sabra_Account"]=="NO NEED TO MAP"]["Tenant_Formated_Account"])]
            for idx_account in dup_tenant_account[:]:
		# Extract records with current index value
                records_idx = PL.loc[idx_account]
                # if all records have the same data, remove the duplicated records, remove this account from dup_tenant_account
                if (records_idx == records_idx.iloc[0]).all(axis=None):
                    PL = pd.concat([PL.loc[idx_account].drop_duplicates().head(1), PL.loc[PL.index != idx_account]])
                    dup_tenant_account.remove(idx_account)  
            if len(dup_tenant_account)>0:
                st.error("Duplicated accounts detected in {} sheet '{}'. Please rectify them to avoid repeated calculations: **{}** ".format(sheet_type_name,sheet_name,", ".join(dup_tenant_account)))
        # Map PL accounts and Sabra account
        #PL,PL_with_detail=Map_PL_Sabra(PL,entity_i) 
        PL=Map_PL_Sabra(PL,entity_i) 
    #return PL,PL_with_detail
    return PL
       

# no cache
def Upload_And_Process(uploaded_file,file_type):
    Total_PL=pd.DataFrame()
    #Total_PL_detail=pd.DataFrame()
    total_entity_list=list(entity_mapping.index)
    Occupancy_in_one_sheet=[]
    BS_in_one_sheet=[]
    account_pool_full=account_mapping.loc[account_mapping["Sabra_Account"]!="NO NEED TO MAP"]["Tenant_Formated_Account"]
    account_pool_patient_days=account_pool.loc[account_pool["Category"]=="Patient Days"]["Tenant_Formated_Account"]	   
    account_pool_balance_sheet=account_pool.loc[account_pool["Category"]=="Balance Sheet"]["Tenant_Formated_Account"]    
    
    # ****Finance and BS in one excel****
    if file_type=="Finance":
        for entity_i in total_entity_list:   # entity_i is the entity code S number
	    # properties in seperate sheet 
            if entity_mapping.loc[entity_i,"Finance_in_separate_sheets"]=="Y":
                PL=Read_Clean_PL_Single(entity_i,"Sheet_Name_Finance",uploaded_file,account_pool_full)
                if Total_PL.shape[0]==0:
                    Total_PL=PL
                else:
                    Total_PL=Total_PL.combine_first(PL)
	    
	# check census data
        for entity_i in total_entity_list: 
            sheet_name_finance=str(entity_mapping.loc[entity_i,"Sheet_Name_Finance"])
            sheet_name_occupancy=str(entity_mapping.loc[entity_i,"Sheet_Name_Occupancy"])
            if not pd.isna(sheet_name_occupancy) \
                and sheet_name_occupancy is not None \
                and sheet_name_occupancy!=" " \
                and sheet_name_occupancy!="nan"	and sheet_name_occupancy!=sheet_name_finance \
                and entity_mapping.loc[entity_i,"Occupancy_in_separate_sheets"]=="Y":
                PL_occ=Read_Clean_PL_Single(entity_i,"Sheet_Name_Occupancy",uploaded_file,account_pool_patient_days) 
                Total_PL=Total_PL.combine_first(PL_occ)
        #BS
        for entity_i in total_entity_list: 
            if  entity_mapping.loc[entity_i,"BS_separate_excel"]=="N": 
                sheet_name_finance=str(entity_mapping.loc[entity_i,"Sheet_Name_Finance"])
                sheet_name_balance=str(entity_mapping.loc[entity_i,"Sheet_Name_Balance_Sheet"])
                if not pd.isna(sheet_name_balance) \
                       and sheet_name_balance!=" " \
                       and sheet_name_balance!="nan" \
                       and sheet_name_balance!=sheet_name_finance \
                       and entity_mapping.loc[entity_i,"Balance_in_separate_sheets"]=="Y":
                    PL_BS=Read_Clean_PL_Single(entity_i,"Sheet_Name_Balance_Sheet",uploaded_file,account_pool_balance_sheet)
                    Total_PL=Total_PL.combine_first(PL_BS)
        
 
	# All the properties are in one sheet	
        sheet_list_finance_in_onesheet = entity_mapping[entity_mapping["Finance_in_separate_sheets"]=="N"]["Sheet_Name_Finance"].unique()
        if len(sheet_list_finance_in_onesheet)>0:
            for sheet_name_finance_in_onesheet in sheet_list_finance_in_onesheet:
                entity_list_finance_in_onesheet=entity_mapping.index[entity_mapping["Sheet_Name_Finance"]==sheet_name_finance_in_onesheet].tolist()	
                PL=Read_Clean_PL_Multiple(entity_list_finance_in_onesheet,"Sheet_Name_Finance",uploaded_file,account_pool_full,sheet_name_finance_in_onesheet)
                if Total_PL.shape[0]==0:
                    Total_PL=PL
                else:
                    Total_PL=Total_PL.combine_first(PL)
	
	# census
        sheet_list_occupancy_in_onesheet = entity_mapping[(entity_mapping["Occupancy_in_separate_sheets"]=="N")&(~pd.isna(entity_mapping["Sheet_Name_Occupancy"]))&(entity_mapping["Sheet_Name_Occupancy"]!="nan")]["Sheet_Name_Occupancy"].unique()
        if len(sheet_list_occupancy_in_onesheet)>0:
            for sheet_name_occupancy_in_onesheet in sheet_list_occupancy_in_onesheet:
                entity_list_occupancy_in_onesheet=entity_mapping.index[entity_mapping["Sheet_Name_Occupancy"]==sheet_name_occupancy_in_onesheet].tolist()	
                PL_Occ=Read_Clean_PL_Multiple(entity_list_occupancy_in_onesheet,"Sheet_Name_Occupancy",uploaded_file,account_pool_patient_days,sheet_name_occupancy_in_onesheet)
                Total_PL=Total_PL.combine_first(PL_Occ)
		    
	# balance sheet
        sheet_list_bs_in_onesheet = entity_mapping[(entity_mapping["Balance_in_separate_sheets"]=="N")&(~pd.isna(entity_mapping["Sheet_Name_Balance_Sheet"]))&(entity_mapping["Sheet_Name_Balance_Sheet"]!="nan")]["Sheet_Name_Balance_Sheet"].unique()
        if len(sheet_list_bs_in_onesheet)>0:
            for sheet_name_bs_in_onesheet in sheet_list_bs_in_onesheet:
                entity_list_bs_in_onesheet=entity_mapping.index[entity_mapping["Sheet_Name_Balance_Sheet"]==sheet_name_bs_in_onesheet].tolist()	
                PL_BS=Read_Clean_PL_Multiple(entity_list_bs_in_onesheet,"Sheet_Name_Balance_Sheet",uploaded_file,account_pool_balance_sheet,sheet_name_bs_in_onesheet)
                Total_PL=Total_PL.combine_first(PL_BS)
		    
    elif file_type=="BS":
        for entity_i in total_entity_list: 
            if entity_mapping.loc[entity_i,"Balance_in_separate_sheets"]=="Y":
                PL_BS=Read_Clean_PL_Single(entity_i,"Sheet_Name_Balance_Sheet",uploaded_file,account_pool_balance_sheet)
                if Total_PL.shape[0]==0:
                    Total_PL=PL_BS
                else:
                    Total_PL=Total_PL.combine_first(PL_BS)

        sheet_list_bs_in_onesheet = entity_mapping[(entity_mapping["Balance_in_separate_sheets"]=="N")&(~pd.isna(entity_mapping["Sheet_Name_Balance_Sheet"]))&(entity_mapping["Sheet_Name_Balance_Sheet"]!="nan")]["Sheet_Name_Balance_Sheet"].unique()
        if len(sheet_list_bs_in_onesheet)>0:
            for sheet_name_bs_in_onesheet in sheet_list_bs_in_onesheet:
                entity_list_bs_in_onesheet=entity_mapping.index[entity_mapping["Sheet_Name_Balance_Sheet"]==sheet_name_bs_in_onesheet].tolist()	
                PL_BS=Read_Clean_PL_Multiple(entity_list_bs_in_onesheet,"Sheet_Name_Balance_Sheet",uploaded_file,account_pool_balance_sheet,sheet_name_bs_in_onesheet)
                if Total_PL.shape[0]==0:
                    Total_PL=PL_BS
                else:
                    Total_PL=Total_PL.combine_first(PL_BS)

    Total_PL = Total_PL.sort_index()  #'ENTITY',"Sabra_Account" are the multi-index of Total_Pl
    return Total_PL
#----------------------------------website widges------------------------------------
config_obj = s3.get_object(Bucket=bucket_PL, Key="config.yaml")
config = yaml.safe_load(config_obj["Body"])
# Creating the authenticator object
authenticator = Authenticate(
        config['credentials'],
        config['cookie']['name'], 
        config['cookie']['key'], 
        config['cookie']['expiry_days'],
        config['preauthorized']
    )

# set button status
button_initial_state={"forgot_password_button":False,"forgot_username_button":False,"submit_report":False}

if 'clicked' not in st.session_state:
    st.session_state.clicked = button_initial_state
	

# login widget
col1,col2=st.columns(2)
with col1:
    authenticator.login('Login', bucket_PL,config,'main')

if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')


#---------------operator account-----------------------
elif st.session_state["authentication_status"] and st.session_state["operator"]!="Sabra":
    operator=st.session_state["operator"]
    st.title(operator)
    menu=["Upload P&L","Manage Mapping","Instructions","Edit Account","Logout"]
    choice=st.sidebar.selectbox("Menu", menu)
    if choice=="Upload P&L":
        if current_month<10:
            current_date=str(current_year)+"0"+str(current_month)
        else:
            current_date=str(current_year)+str(current_month)
        if 'selected_year' not in st.session_state:
            st.session_state.selected_year = current_year
        if 'selected_month' not in st.session_state:
            st.session_state.selected_month = '01'
        global reporting_month,reporting_month_label,tenant_account_col,date_header
        BPC_pull,entity_mapping,account_mapping=Initial_Mapping(operator)
        reporting_month_label=True  
        tenant_account_col=10000
        date_header=[[0],0,[]]
        col1,col2=st.columns([3,1])
        # Calculate the list of years and their indices
        years_range = list(range(current_year, current_year - 2, -1))
        # Calculate the list of months and their indices
        months_range = [str(month).zfill(2) for month in range(1, 13)]
        if "Y" in entity_mapping["BS_separate_excel"][~pd.isna(entity_mapping["BS_separate_excel"])].values:             
            BS_separate_excel="Y"
        else:
            BS_separate_excel="N"
        with col1:
            with st.form("upload_form", clear_on_submit=True):
                st.subheader("Select reporting month:") 
                col3,col4=st.columns([1,1])
                with col3:
                    selected_year = st.selectbox("Year", years_range,index=years_range.index(st.session_state.selected_year))
                with col4:    
                    selected_month = st.selectbox("Month", months_range,index=months_range.index(st.session_state.selected_month))
   
                with col3:
                    #st.markdown("<p style='font-size:20px;'>Upload P&L:</p>", unsafe_allow_html=True)
                    st.subheader("Upload P&L:")
                    uploaded_finance=st.file_uploader(":star: :red[Only XLSX accepted] :star:",type={"xlsx"},accept_multiple_files=False,key="Finance_upload")
                with col4:
                    if BS_separate_excel=="Y":
                        st.subheader("Upload Balance Sheet:")
                        #st.markdown("<p style='font-size:20px;'>Upload Balance Sheet:</p>", unsafe_allow_html=True)
                        uploaded_BS=st.file_uploader("",type={"xlsx"},accept_multiple_files=False,key="BS_upload")
                submitted = st.form_submit_button("Upload")
                if submitted:
	            # clear cache for every upload
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.session_state.clicked = button_initial_state
                    st.session_state.selected_year = selected_year
                    st.session_state.selected_month = selected_month
                    reporting_month=str(selected_year)+str(selected_month)
        if uploaded_finance:
            with col3:
                st.markdown("✔️ :green[P&L selected]")
        else:
            st.write("P&L wasn't upload.")
            st.stop()

        reporting_month=str(selected_year)+str(selected_month)
        if reporting_month>=current_date:
            st.error("The reporting month should precede the current month.")
            st.stop()
        filtered_months =sorted([x for x in BPC_pull.columns if x <reporting_month],reverse=True)
        BPC_pull=BPC_pull[["Property_Name"]+filtered_months[:previous_monthes_comparison]]    
        entity_mapping=entity_mapping.loc[((entity_mapping["DATE_ACQUIRED"]<=reporting_month) &((pd.isna(entity_mapping["DATE_SOLD_PAYOFF"]))| (entity_mapping["DATE_SOLD_PAYOFF"]>=reporting_month))),]
        if "Y" in entity_mapping["BS_separate_excel"][~pd.isna(entity_mapping["BS_separate_excel"])].values:                     
            BS_separate_excel="Y"
            if uploaded_BS:
                with col4:
                    st.markdown("✔️ :green[Balance sheet selected]")
            elif not uploaded_BS:
                st.write("Balance sheet wasn't upload.")
                st.stop()
        else:
            BS_separate_excel="N"


        account_pool=account_mapping[["Sabra_Account","Tenant_Formated_Account"]].merge(BPC_Account[["BPC_Account_Name","Category"]], left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")
	    
        if BS_separate_excel=="N":  # Finance/BS are in one excel
            entity_mapping=Check_Sheet_Name_List(uploaded_finance,"Finance")	 
            #Total_PL,Total_PL_detail=Upload_And_Process(uploaded_finance,"Finance")
	 
            with st.spinner('Wait for P&L processing'):
                Total_PL=Upload_And_Process(uploaded_finance,"Finance")
        elif BS_separate_excel=="Y":     # Finance/BS are in different excel 
            entity_mapping=Check_Sheet_Name_List(uploaded_finance,"Finance")
            entity_mapping=Check_Sheet_Name_List(uploaded_BS,"BS")

            # process Finance 
            with st.spinner('Wait for P&L processing'):
                #Total_PL,Total_PL_detail=Upload_And_Process(uploaded_finance,"Finance")
                Total_PL=Upload_And_Process(uploaded_finance,"Finance")
	    # process BS 
            with st.spinner('Wait for Balance Sheet processing'):
                #Total_BL,Total_BL_detail=Upload_And_Process(uploaded_BS,"BS")
                Total_BL=Upload_And_Process(uploaded_BS,"BS")
	    # combine Finance and BS
            Total_PL=Total_PL.combine_first(Total_BL)
            #Total_PL_detail=Total_PL_detail.combine_first(Total_BL_detail)
        if len(Total_PL.columns)==1:
            Total_PL.columns=[reporting_month]

        elif len(Total_PL.columns)>1:  # there are previous months in P&L
            #diff_BPC_PL,diff_BPC_PL_detail=Compare_PL_Sabra(Total_PL,Total_PL_detail,reporting_month)
            diff_BPC_PL=Compare_PL_Sabra(Total_PL,reporting_month)
   
	# 1 Summary
        View_Summary()
       	

        # upload reporting month data to AWS
        st.button("******Confirm and upload {} {}-{} reporting******".format(operator,reporting_month[4:6],reporting_month[0:4]),on_click=clicked, args=["submit_report"],key='reporting_month')  
       
        # 2 Discrepancy of Historic Data
        with st.expander("Discrepancy for Historic Data",expanded=True):
            ChangeWidgetFontSize('Discrepancy for Historic Data', '25px')
            if len(Total_PL.columns)>1:	
                with st.spinner("********Running discrepancy check********"): 
                    View_Discrepancy()
                
            elif len(Total_PL.columns)==1:
                st.write("There is no previous month data in tenant P&L")
        Submit_Upload_Latestmonth()      
       

    elif choice=="Manage Mapping":
        BPC_pull,entity_mapping,account_mapping=Initial_Mapping(operator)
        with st.expander("Manage Property Mapping" ,expanded=True):
            ChangeWidgetFontSize('Manage Property Mapping', '25px')
            entity_mapping=Manage_Entity_Mapping(operator)
        with st.expander("Manage Account Mapping",expanded=True):
            ChangeWidgetFontSize('Manage Account Mapping', '25px')
            col1,col2=st.columns(2)
            with col1:
                new_tenant_account=st.text_input("Enter new account and press Enter to apply. Use commas to separate them if there are multiple accounts.")
                
                if new_tenant_account:
                    new_tenant_account_list=list(set(map(lambda x:x.strip(),new_tenant_account.split(",") )))
                    duplicate_accounts=list(filter(lambda x:x.upper() in list(account_mapping['Tenant_Formated_Account']),new_tenant_account_list))
                   
                    if len(duplicate_accounts)>1:
                        st.write("{} are already existed in mapping list and will be skip.".format(",".join(duplicate_accounts)))
                    elif len(duplicate_accounts)==1:
                        st.write("{} is already existed in mapping list and will be skip.".format(duplicate_accounts[0]))
		
		    # remove duplicated accounts
                    new_tenant_account_list=list(set(new_tenant_account_list) - set(duplicate_accounts))
                    if len(new_tenant_account_list)==0:
                        st.stop()
                    account_mapping=Manage_Account_Mapping(new_tenant_account_list)
                    Update_File_Onedrive(mapping_path,account_mapping_filename,account_mapping,operator,None,account_mapping_str_col)
			
    elif choice=='Instructions':
        # insert Video
        video=s3.get_object(Bucket=bucket_mapping, Key="Sabra App video.mp4")
        st.video(BytesIO(video['Body'].read()), format="mp4", start_time=0)
	    
    elif choice=="Edit Account": 
	# update user details widget
        try:
            authenticator.update_user_details(st.session_state["username"], 'Update user details',config)

        except Exception as e:
            st.error(e)

    elif choice=="Logout":
        authenticator.logout('Logout', 'main')
# ----------------for Sabra account--------------------	    
elif st.session_state["authentication_status"] and st.session_state["operator"]=="Sabra":
    operator_list=Read_CSV_From_Onedrive(mapping_path,operator_list_filename)
    menu=["Review Monthly reporting","Review New Mapping","Edit Account","Register","Logout"]
    choice=st.sidebar.selectbox("Menu", menu)

    if choice=="Edit Account":
	# update user details widget
        try:
            if authenticator.update_user_details(st.session_state["username"], 'Update user details',config):
                st.success('Updated successfully')
        except Exception as e:
            st.error(e)
    
    elif choice=="Register":
        col1,col2=st.columns(2)
        with col1:
            operator= st.selectbox('Select Operator',(operator_list["Operator"]))
        try:
            if authenticator.register_user('Register for '+operator, operator, config, preauthorization=False):
                st.success('Registered successfully')
        except Exception as e:
            st.error(e)
		
    elif choice=="Logout":
        authenticator.logout('Logout', 'main')
	    
    elif choice=="Review New Mapping":
        with st.expander("Review new mapping" ,expanded=True):
            ChangeWidgetFontSize('Review new mapping', '25px')
            account_mapping =Read_CSV_From_Onedrive(mapping_path,account_mapping_filename,account_mapping_str_col)
            un_confirmed_account=account_mapping[account_mapping["Confirm"]=="N"]
            if un_confirmed_account.shape[0]==0:
                st.write("There is no new mapping.")
                st.write(un_confirmed_account)
            else:
                un_confirmed_account['Index'] = range(1, len(un_confirmed_account) + 1)
                un_confirmed_account=un_confirmed_account[["Index","Operator","Tenant_Account","Sabra_Account","Sabra_Second_Account"]]
                gd = GridOptionsBuilder.from_dataframe(un_confirmed_account)
                gd.configure_column("Index",headerName="Select", width=60,headerCheckboxSelection = True)
                gd.configure_selection(selection_mode='multiple', use_checkbox=True)
                gd.configure_column("Tenant_Account", headerName="Tenant Account",width=250)
                gd.configure_column("Sabra_Account", headerName="Sabra Account",width=170)
                gd.configure_column("Sabra_Second_Account", headerName="Sabra Second Account",width=130)
                gd.configure_column("Operator",width=80)
                grid_table = AgGrid(un_confirmed_account,
			    gridOptions=gd.build(),
			    fit_columns_on_grid_load=True,
        		    theme = "streamlit",
                            update_mode=GridUpdateMode.SELECTION_CHANGED)
                selected_row = grid_table["selected_rows"]

                col1,col2=st.columns([1,4])
                with col1:
                    confirm_button=st.button("Confirm new mappings")
                with col2:
                    download_report(un_confirmed_account,"new mappings")
                if confirm_button:
                    if selected_row:
                        if len(selected_row)==un_confirmed_account.shape[0]: # select all
                            account_mapping["Confirm"]=None 
                        else:#select part
                            for i in range(len(selected_row)):
                                tenant_account=un_confirmed_account[un_confirmed_account["Index"]==selected_row[i]["Index"]]["Tenant_Account"].item()
                                account_mapping.loc[account_mapping["Tenant_Account"]==tenant_account,"Confirm"]=None
                        # save account_mapping 
                        if Save_as_CSV_Onedrive(account_mapping,path,account_mapping_filename):    
                            st.success("Selected mappings have been archived successfully")
                        else:
                            st.error("Can't save the change, please contact Sha Li.")
                    else:
                        st.error("Please select mapping to confirm")
        with st.expander("Review tenant mapping" ,expanded=True):
            ChangeWidgetFontSize('Review tenant mapping', '25px')
            col1,col2=st.columns(2)
            select_operator=list(operator_list["Operator"])
            select_operator[0]="Total"
            with col1:
                selected_operator= st.selectbox('Select Operator',select_operator)
            if selected_operator:
                if selected_operator!="Total":
                    operator_mapping=account_mapping.loc[account_mapping["Operator"]==selected_operator,:]
                    st.write(operator_mapping)
                    download_report(operator_mapping,"{} mapping".format(selected_operator))
                else:
                    st.write(account_mapping)
                    download_report(account_mapping,"Total tenant mapping")

    elif choice=="Review Monthly reporting":
            st.subheader("Summary")
            data=Read_CSV_From_Onedrive(master_template_path,monthly_reporting_filename)
            #if data is None:  # empty file
            if True:
                data=data[list(filter(lambda x:"Unnamed" not in x and 'index' not in x ,data.columns))]
                data["Upload_Check"]=""
                # summary for operator upload
                data["TIME"]=data["TIME"].apply(lambda x: "{}.{}".format(str(x)[0:4],month_abbr[int(str(x)[4:6])]))
                col1,col2,col3=st.columns((2,1,1))
                summary=data[["TIME","Operator","Latest_Upload_Time"]].drop_duplicates()
                summary = summary.sort_values(by="Latest_Upload_Time", ascending=False)

                with col1:
                    st.dataframe(
			    summary,
			    column_config={
			        "TIME": "Reporting month",
			        "Latest_Upload_Time":"Latest submit time"},
			    hide_index=True)
                st.write("")
                st.subheader("Download reporting data with EPM Formula")    
		    
                # add average column for each line , average is from BPC_pull
                BPC_pull=Read_CSV_From_Onedrive(mapping_path,BPC_pull_filename)
                BPC_pull.columns=list(map(lambda x :str(x), BPC_pull.columns))
                data=data.merge(BPC_pull[["ENTITY","Sabra_Account","Mean"]], on=["ENTITY","Sabra_Account"],how="left")	
		# add "GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE" from entity_mapping
                entity_mapping=Read_CSV_From_Onedrive(mapping_path,entity_mapping_filename)
                data=data.merge(entity_mapping[["ENTITY","GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE"]],on="ENTITY",how="left")

                data=EPM_Formula(data,"Amount")	
                download_file=data.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download reporting data",data=download_file,file_name="Operator reporting data.csv",mime="text/csv")
