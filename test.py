import pandas as pd
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
import json
import yaml
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
from msal import ConfidentialClientApplication
import requests
s3 = boto3.client('s3')

#---------------------------define parameters--------------------------
st.set_page_config(
   initial_sidebar_state="expanded",
    layout="wide")
placeholder = st.empty()
st.title("Sabra HealthCare Monthly Reporting App")
sheet_name_discrepancy="Discrepancy_Review"
bucket_mapping="sabramapping"
bucket_PL="operatorpl"
account_mapping_filename="Account_Mapping.csv"
BPC_pull_filename="BPC_Pull.csv"
entity_mapping_filename ="Entity_Mapping.csv"
discrepancy_path="Total_Diecrepancy_Review.csv"
monthly_reporting_path="Total monthly reporting.csv"
operator_list_path="Operator_list.csv"
BPC_account_path="Sabra_account_list.csv"
#One drive authority. Set application details
client_id = 'bc5f9d8d-eb35-48c3-be6d-98812daab3e3'
client_secret = '1h28Q~Tw-xwTMPW9w0TqjbeaOhkYVDrDQ8VHcbkd'
tenant_id = '71ffff7c-7e53-4daa-a503-f7b94631bd53'
authority = 'https://login.microsoftonline.com/' + tenant_id
# shali's use id of onedrive
user_id = '62d4a23f-e25f-4da2-9b52-7688740d9d48'

def Upload_to_Onedrive(uploaded_file,file_name):

    # Read the content of the uploaded file
    #file_content = uploaded_file.read()
    file_content = uploaded_file.read()

        # Use BytesIO to create a stream from the file content
    file_stream = BytesIO(file_content)


    # Use BytesIO to create a stream from the file content
    file_stream = BytesIO(file_content)

    # Acquire a token using client credentials flow
    app = ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret)

    token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    access_token = token_response['access_token']
    
    # Set the API endpoint and headers
    api_url = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/items/root:/Documents/{file_name}:/content'
    headers = {
    'Authorization': 'Bearer ' + access_token,}

    # Make the request to upload the file
    response = requests.put(api_url, headers=headers, data=file_stream)
    st.write(f"Status code for {uploaded_file.name}: {response.status_code}")
    st.write(response.json())

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

# Function to update the value in session state
def clicked(button_name):
    st.session_state.clicked[button_name] = True
	
# For updating account_mapping, entity_mapping, latest_month_data, only for operator use
def Update_File_inS3(bucket,key,new_data,operator,value_name=False):  # replace original data
    original_file =s3.get_object(Bucket=bucket, Key=key)
    try:
        original_data=pd.read_csv(BytesIO(original_file['Body'].read()),header=0)
        original_data=original_data.loc[new_data.columns,:]
        empty_file=False
    except:
        original_data=pd.DataFrame()
        empty_file=True
    if not empty_file:	    
        if "TIME" in original_data.columns and "TIME" in new_data.columns:
            original_data.TIME = original_data.TIME.astype(str)
	    # remove original data by operator and month 
            months_of_new_data=new_data["TIME"].unique()
            original_data = original_data.drop(original_data[(original_data['Operator'] == operator)&(original_data['TIME'].isin(months_of_new_data))].index)
        elif "TIME" not in original_data.columns and "TIME" not in new_data.columns:
            original_data = original_data.drop(original_data[original_data['Operator'] == operator].index)

        
    # append new data to original data
    new_data=new_data.reset_index(drop=False)
    updated_data = pd.concat([original_data,new_data])
    if value_name is not False: # set formula 
        updated_data=EPM_Formula(updated_data,value_name)
    return Save_CSV_ToS3(updated_data,bucket,key)


#@st.cache_data
def Initial_Paramaters(operator):
    # drop down list of operator
    if operator!="Sabra":
        BPC_pull=Read_CSV_FromS3(bucket_mapping,BPC_pull_filename)
        BPC_pull=BPC_pull[BPC_pull["Operator"]==operator]
        BPC_pull=BPC_pull.set_index(["ENTITY","ACCOUNT"])
        BPC_pull.columns=list(map(lambda x :str(x), BPC_pull.columns))
                  
        month_dic={10:["october","oct","10/","-10","/10","10"],11:["november","nov","11/","-11","/11","11"],12:["december","dec","12/","-12","/12","12"],1:["january","jan","01/","1/","-1","-01","/1","/01"],\
                   2:["february","feb","02/","2/","-2","-02","/2","/02"],3:["march","mar","03/","3/","-3","-03","/3","/03"],4:["april","apr","04/","4/","-4","-04","/4","/04"],\
                   5:["may","05/","5/","-5","-05","/5","/05"],6:["june","jun","06/","6/","-06","-6","/6","/06"],\
                   7:["july","jul","07/","7/","-7","-07","/7","/07"],8:["august","aug","08/","8/","-8","-08","/8","/08"],9:["september","sep","09/","9/","-09","-9","/9","/09"]}
        year_dic={2021:["2021","21"],2022:["2022","22"],2023:["2023","23"],2024:["2024","24"],2025:["2025","25"],2026:["2026","26"],2019:["2019","19"],2018:["2018","18"],2020:["2020","20"]} 

    else:
        st.stop()
    return BPC_pull,month_dic,year_dic


#@st.cache_resource
def Initial_Mapping(operator):
    # read account mapping
    account_mapping_all = Read_CSV_FromS3(bucket_mapping,account_mapping_filename)  
    account_mapping = account_mapping_all.loc[account_mapping_all["Operator"]==operator]
    account_mapping.loc["Tenant_Formated_Account":]=list(map(lambda x:x.upper().strip(),account_mapping.loc["Tenant_Account":]))
    account_mapping=account_mapping[["Operator","Sabra_Account","Sabra_Second_Account","Tenant_Account","Tenant_Formated_Account","Conversion"]] 
    # read property mapping
    entity_mapping=Read_CSV_FromS3(bucket_mapping,entity_mapping_filename)
    entity_mapping=entity_mapping.reset_index(drop=True)
    entity_mapping=entity_mapping[entity_mapping["Operator"]==operator]
    entity_mapping=entity_mapping.set_index("ENTITY")
    return entity_mapping,account_mapping


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
    BPC_Account = Read_CSV_FromS3(bucket_mapping, BPC_account_path)
 
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
# setting for page
@st.cache_data
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



@st.cache_data
def Identify_Tenant_Account_Col(PL,sheet_name,sheet_type):
    #search tenant account column in P&L, return col number of tenant account
    account_pool=account_mapping[["Sabra_Account","Tenant_Formated_Account"]].merge(BPC_Account[["BPC_Account_Name","Category"]], left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")	       
    if sheet_type=="Sheet_Name_Finance":
        account_pool=account_pool.loc[account_pool["Sabra_Account"]!="NO NEED TO MAP"]["Tenant_Formated_Account"]
    elif sheet_type=="Sheet_Name_Occupancy": 
        account_pool=account_pool.loc[account_pool["Category"]=="Patient Days"]["Tenant_Formated_Account"]	       
    elif sheet_type=="Sheet_Name_Balance_Sheet":
        account_pool=account_pool.loc[account_pool["Category"]=="Balance Sheet"]["Tenant_Formated_Account"]
    
    for tenantAccount_col_no in range(0,PL.shape[1]):
        #trim and upper case 
        candidate_col=list(map(lambda x: str(x).strip().upper() if x==x else x,PL.iloc[:,tenantAccount_col_no]))
        #find out how many tenant accounts match with account_pool
        match=[x in candidate_col for x in account_pool]
        #If 10% of accounts match with account_mapping list, identify this col as tenant account.
        
        if len(match)>0 and sum(x for x in match)/len(match)>0.1:
            return tenantAccount_col_no  
        else:
            # it is the wrong account column, continue to check next column
            continue
            
    st.error("Fail to identify tenant accounts column in sheet—— '"+sheet_name+"'")
    st.stop()


def download_report(df,button_display):
    download_file=df.to_csv(index=False).encode('utf-8')
    return st.download_button(label="Download "+button_display,data=download_file,file_name=button_display+".csv",mime="text/csv")
    
def Get_Year(single_string):
    if single_string!=single_string or single_string==None or type(single_string)==float:
        return 0,""
    else:
        for Year in year_dic.keys():
            for Year_keyword in year_dic[Year]:
                if Year_keyword in single_string:
                    return Year,Year_keyword
        return 0,""

def Get_Month_Year(single_string):
    if single_string!=single_string or single_string==None or type(single_string)==float:
        return 0,0
    if type(single_string)==datetime:
        return int(single_string.month),int(single_string.year)

    single_string=str(single_string).lower()
    Year,Year_keyword=Get_Year(single_string)
    
    # remove year from string, remove days from string
    single_string=single_string.replace(Year_keyword,"").replace("30","").replace("31","").replace("28","").replace("29","")
    
    for Month in month_dic.keys() :#[01,02,03...12]
        for  Month_keyword in month_dic[Month]: #['december','dec','12',...]
            if Month_keyword in single_string:
                remaining=single_string.replace(Month_keyword,"").replace("/","").replace("-","").replace(" ","").replace("_","")
                
                #if there are more than 3 other char in the string, this string is not month 
                if len(remaining)>=3:
                    return 0,0
                else:   
                    return Month,Year
            # string doesn't contain month keyword, continue to next month keyword
            else:
                continue
    # didn't find month. return month as 0
    return 0,Year    
    
def Month_continuity_check(month_list):
    inv=[]
    month_list=list(filter(lambda x:x!=0,month_list))
    month_len=len(month_list)
    if month_len==0:
        return False
    else:
        inv=[int(month_list[month_i+1])-int(month_list[month_i]) for month_i in range(month_len-1) ]
        #there are at most two types of difference in the month list which are in 1,-1,11,-11 
        if  len(set(inv))<=2 and all([x in [1,-1,11,-11] for x in set(inv)]):
            return True  # Month list is continous 
        else:
            return False # Month list is not continous 
            
def Year_continuity_check(year_list):
    inv=[]
    year_list=list(filter(lambda x:x!=0,year_list))
    year_len=len(year_list)
    if year_len==0:
        return False
    else:
        inv=[int(year_list[year_i+1])-int(year_list[year_i]) for year_i in range(year_len-1)]
        if len(set(inv))<=2 and all([x in [1,0,-1] for x in set(inv)]):
            return True         #years are continous
        else:
            return False

# add year to month_header: identify current year/last year giving a list of month
def Add_year_to_header(month_list):
    available_month=list(filter(lambda x:x!=0,month_list))
    today=date.today()
    current_year= today.year
    last_year=current_year-1
    if len(available_month)==1:
        
        if datetime.strptime(available_month[0]+"/01/"+current_year,'%m/%d/%Y').date()<today:
            year=current_year
        else:
            year=today.year-1
        return year
     
    year_change=0     
    # month decending  #and available_month[0]<today.month
    if (available_month[0]>available_month[1] and available_month[0]!=12) or (available_month[0]==1 and available_month[1]==12) : 
        date_of_assumption=datetime.strptime(str(available_month[0])+"/01/"+str(current_year),'%m/%d/%Y').date()
        if date_of_assumption<today and date_of_assumption.month<today.month:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(len(available_month)):
            available_month[i]=report_year_start-year_change
            if i<len(available_month)-1 and available_month[i+1]==12:
                year_change+=1
            
    # month ascending
    elif (available_month[0]<available_month[1] and available_month[0]!=12) or (available_month[0]==12 and available_month[1]==1): #and int(available_month[-1])<today.month
        date_of_assumption=datetime.strptime(str(available_month[-1])+"/01/"+str(current_year),'%m/%d/%Y').date()    
        if date_of_assumption<today:
            report_year_start=current_year
        elif date_of_assumption>=today:
            report_year_start=last_year
        for i in range(-1,len(available_month)*(-1)-1,-1):
   
            available_month[i]=report_year_start-year_change
            if i>len(available_month)*(-1) and available_month[i-1]==12:
                #print("year_change",year_change)
                year_change+=1
    else:
        return False
 
    j=0
    for i in range(len(month_list)):
        if month_list[i]!=0:
            month_list[i]=available_month[j]
            j+=1
    return month_list  

# search for the Month/year row and return row number

@st.cache_data
def Identify_Month_Row(PL,tenantAccount_col_no,sheet_name):
    PL_row_size=PL.shape[0]
    PL_col_size=PL.shape[1]
    search_row_size=min(15,PL_row_size)
    month_table=pd.DataFrame(0,index=range(search_row_size), columns=range(PL_col_size))
    year_table=pd.DataFrame(0,index=range(search_row_size), columns=range(PL_col_size))

    for row_i in range(search_row_size):
        for col_i in range(PL_col_size):
            month_table.iloc[row_i,col_i],year_table.iloc[row_i,col_i]=Get_Month_Year(PL.iloc[row_i,col_i])       
    year_count=[]        
    month_count=[]
    max_len=0
    for row_i in range(search_row_size):
        # save the number of valid months of each row to month_count
        valid_month=list(filter(lambda x:x!=0,month_table.iloc[row_i,]))
        valid_year=list(filter(lambda x:x!=0,year_table.iloc[row_i,]))
        month_count.append(len(valid_month))
        year_count.append(len(valid_year))
        
    # can't find month keyword in any rows
    if all(map(lambda x:x==0,month_count)):
        st.error("Can't identify month/year columns in sheet——'"+sheet_name+"'")   
        st.stop()
        
    month_sort_index = np.argsort(np.array(month_count))
    year_sort_index = np.argsort(np.array(year_count))
    for month_index_i in range(-1,-4,-1): # only check three of the most possible rows
        #month_sort_index[-1] is the index number of month_count in which has max month count
        #month_row_index is also the index/row number of PL
        month_row_index=month_sort_index[month_index_i]
        if month_count[month_row_index]>1:
            month_row=list(month_table.iloc[month_row_index,])

	    # if True, it is the correct month row
            if Month_continuity_check(month_row):
                
                for year_index_i in range(0,-4,-1):
                    if year_index_i==0:
                        #in most case,year and month are in the same row, so first check month row
                        year_row_index=month_row_index
                    elif year_sort_index[year_index_i]!=month_row_index:  
                        year_row_index=year_sort_index[year_index_i]
                        #month row and year row is supposed to be adjacent
                        if abs(year_row_index-month_row_index)>2:
                            continue
                    
                    year_row=list(year_table.iloc[year_row_index,])
		            # if month and year are not in the same places in the columns, year_row is not the correct one
                    if not all([year_row[i]==month_row[i] if month_row[i]==0 else year_row[i]!=0 for i in range(len(month_row))]):
                        continue
            
                    # check validation of year
                    if Year_continuity_check(year_row) and year_count[year_row_index]==month_count[month_row_index]:
                        PL_date_header=year_table.iloc[year_row_index,].apply(lambda x:str(int(x)))+\
                        month_table.iloc[month_row_index,].apply(lambda x:"" if x==0 else "0"+str(int(x)) if x<10 else str(int(x)))
                        return PL_date_header,month_row_index
                    
                    # all the year rows are not valid, add year to month
                    else:
                        continue

		        # all the year rows are not valid, add year to month
                year_table.iloc[year_row_index,]=Add_year_to_header(list(month_table.iloc[month_row_index,]))
                PL_date_header=year_table.iloc[year_row_index,].apply(lambda x:str(int(x)))+month_table.iloc[month_row_index,].apply(lambda x:"" if x==0 else "0"+str(int(x)) if x<10 else str(int(x)))
                original_header=PL.iloc[month_row_index,]
                
                d_str = ''
                for i in range(len(PL_date_header)):
                        if PL_date_header[i]==0 or PL_date_header[i]=="0":
                            continue
                        else:
                            date=str(PL_date_header[i][4:6])+"/"+str(PL_date_header[i][0:4])
                            d_str +=",  "+str(original_header[i])+" — "+ date
                
                st.warning("Warning: Fail to identify 'year' in the month header of sheet '"+sheet_name+"'. Filled year as:")
                st.markdown(d_str[1:])
                return PL_date_header,month_sort_index[month_index_i]
                        
            # month is not continuous, check next
            else:
                continue
                
        # only one month in header:month and year must exist for one month header
        elif month_count[month_sort_index[month_index_i]]==1:
            # month and year must match 
            #st.write("There is only one month in sheet——'"+sheet_name+"'")
            col_month=0
            #col_month is the col number of month
            while(month_table.iloc[month_sort_index[month_index_i],col_month]==0):
                col_month+=1
                
            #if there is no year in month header, continue 
            if  year_table.iloc[month_sort_index[month_index_i],col_month]==0:
                continue
           
            count_num=0
            count_str=0
            count_non=0
            for row_month in range(month_sort_index[month_index_i],PL.shape[0]):
                if PL.iloc[row_month,col_month]==None or pd.isna(PL.iloc[row_month,col_month]) or PL.iloc[row_month,col_month]=="":
                    count_non+=1
                    continue
                if type(PL.iloc[row_month,col_month])==float or type(PL.iloc[row_month,col_month])==int:
                    count_num+=1
                else:
                    count_str+=1
                # count_num is count of numous row under month header. count_str is the count of character data under month header
                # for a real month column, numous data is supposed to be more than character data
            if count_str>0 and (count_num+count_non)/count_str<0.8:
                continue
                
            else:
                PL_date_header=year_table.iloc[month_sort_index[month_index_i],].apply(lambda x:str(int(x)))+\
                        month_table.iloc[month_sort_index[month_index_i],].apply(lambda x:"" if x==0 else "0"+str(int(x)) if x<10 else str(int(x)))
                        
                return PL_date_header,month_sort_index[month_index_i]
    st.error("Can't identify date row in P&L for sheet: '"+sheet_name+"'")
    st.stop()

#@st.cache_data(experimental_allow_widgets=True)
def Manage_Entity_Mapping(operator):
    global entity_mapping
    #all the properties are supposed to be in entity_mapping. 
    entity_mapping_updation=pd.DataFrame(columns=["Property_Name","Sheet_Name_Finance","Sheet_Name_Occupancy","Sheet_Name_Balance_Sheet"])
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
        st.write(entity_mapping)
        download_report(entity_mapping[["Property_Name","Sheet_Name_Finance","Sheet_Name_Occupancy","Sheet_Name_Balance_Sheet"]],"Properties Mapping_{}".format(operator))
        # update entity_mapping in S3     
        Update_File_inS3(bucket_mapping,entity_mapping_filename,entity_mapping,operator)   
        return entity_mapping

@st.cache_data(experimental_allow_widgets=True)
def Manage_Account_Mapping(new_tenant_account):
    with st.form(key=new_tenant_account):
        col1,col2=st.columns(2) 
        with col1:
            st.write("Sabra main account")
            Sabra_main_account=streamlit_tree_select.tree_select(parent_hierarchy_main,only_leaf_checkboxes=True,key=new_tenant_account) 
        with col2:
            st.write("Sabra second account")
            Sabra_second_account= streamlit_tree_select.tree_select(parent_hierarchy_second,only_leaf_checkboxes=True,key=new_tenant_account+"1")
        submitted = st.form_submit_button("Submit")  
    if submitted:
        if len(Sabra_main_account['checked'])==1:
            Sabra_main_account_value=Sabra_main_account['checked'][0].upper()          
        elif len(Sabra_main_account['checked'])>1:
            st.warning("Only one to one mapping is allowed.")
            st.stop()
        elif Sabra_main_account['checked']==[] and Sabra_second_account['checked']==[]:
            st.warning("Please select Sabra account for '{}'".format(new_tenant_account))
            st.stop()
        elif Sabra_main_account['checked']==[]:
            Sabra_main_account_value=''
            
        if Sabra_second_account['checked']==[]:
            Sabra_second_account_value=''
        elif len(Sabra_second_account['checked'])==1:
            Sabra_second_account_value=Sabra_second_account['checked'][0].upper()
        elif len(Sabra_second_account['checked'])>1:
            st.warning("Only one to one mapping is allowed.")
            st.stop()
    else:
        st.stop()
                
    if Sabra_main_account_value=="NO NEED TO MAP":
        st.success("{} was successfully saved to 'No need to map' list.".format(new_tenant_account))
    elif Sabra_main_account_value:
        st.success("Successfully mapped '{}' to '{}'".format(new_tenant_account,Sabra_main_account_value))
    return Sabra_main_account_value,Sabra_second_account_value     


@st.cache_data
def Map_PL_Sabra(PL,entity):
    # remove no need to map from account_mapping
    main_account_mapping=account_mapping.loc[list(map(lambda x:x==x and x.upper()!='NO NEED TO MAP',account_mapping["Sabra_Account"])),:]

    #concat main accounts with second accounts
    second_account_mapping=account_mapping.loc[(account_mapping["Sabra_Second_Account"]==account_mapping["Sabra_Second_Account"])&(account_mapping["Sabra_Second_Account"]!="NO NEED TO MAP")][["Sabra_Second_Account","Tenant_Formated_Account","Tenant_Account","Conversion"]].\
                           rename(columns={"Sabra_Second_Account": "Sabra_Account"})
    
    PL.index.name="Tenant_Account"
    PL["Tenant_Formated_Account"]=list(map(lambda x:x.upper() if type(x)==str else x,PL.index))
 
    PL=pd.concat([PL.merge(second_account_mapping,on="Tenant_Formated_Account",how='right'),PL.merge(main_account_mapping[main_account_mapping["Sabra_Account"]==main_account_mapping["Sabra_Account"]]\
                                            [["Sabra_Account","Tenant_Formated_Account","Tenant_Account","Conversion"]],on="Tenant_Formated_Account",how='right')])

    PL=PL.reset_index(drop=True)
    month_cols=list(filter(lambda x:str(x[0:2])=="20",PL.columns))
    for i in range(len(PL.index)):
        conversion=PL.loc[i,"Conversion"]
        if conversion!=conversion:
            continue
        else:
            for month in month_cols:
                before_conversion=PL.loc[i,month]
               
                if before_conversion!=before_conversion:
                    continue
                elif conversion=="/monthdays":		
                    PL.loc[i,month]=before_conversion/monthrange(int(str(month)[0:4]), int(str(month)[4:6]))[1]
                elif conversion[0]=="*":
                    PL.loc[i,month]= before_conversion*float(conversion.split("*")[1])


    PL=PL.drop(["Tenant_Formated_Account","Conversion"], axis=1)
    
    PL_with_detail=copy.copy(PL)
    PL_with_detail["Entity"]=entity
    PL_with_detail=PL_with_detail.set_index(['Entity', 'Sabra_Account',"Tenant_Account"])
    PL=PL.set_index("Sabra_Account",drop=True)
    PL=PL.drop(["Tenant_Account"], axis=1)
    # group by Sabra_Account
    PL=PL.groupby(by=PL.index).sum().replace(0,None)
    PL.index=[[entity]*len(PL.index),list(PL.index)]
    return PL,PL_with_detail
    
@st.cache_data
def Compare_PL_Sabra(Total_PL,PL_with_detail,latest_month,month_list):
    PL_with_detail=PL_with_detail.reset_index(drop=False)
    diff_BPC_PL=pd.DataFrame(columns=["TIME","ENTITY","Sabra_Account","Sabra","P&L","Diff (Sabra-P&L)","Diff_Percent"])
    diff_BPC_PL_detail=pd.DataFrame(columns=["Entity","Sabra_Account","Tenant_Account","Month","Sabra","P&L Value","Diff (Sabra-P&L)",""])
    
    if len(month_list)>2:  # only compare 2 months
        month_list=month_list[-2:]
	    
    for entity in entity_mapping.index:
        for timeid in month_list: 
	    # if this entity don't have data for this timeid(new/transferred property), skip to next month
            if all(list(map(lambda x:x!=x,Total_PL.loc[entity,][timeid]))):
                break
            for matrix in BPC_Account.loc[(BPC_Account["Category"]!="Balance Sheet")]["BPC_Account_Name"]: 
                try:
                    BPC_value=int(BPC_pull.loc[entity,matrix][timeid+'00'])
                except:
                    BPC_value=0
                try:
                    PL_value=int(Total_PL.loc[entity,matrix][timeid])
                except:
                    PL_value=0
                if BPC_value==0 and PL_value==0:
                    continue
                diff=BPC_value-PL_value
                diff_percent=abs(diff)/max(abs(PL_value),abs(BPC_value))*100
                if diff_percent>=1: 
                    # for diff_BPC_PL			
                    diff_single_record=pd.DataFrame({"TIME":timeid,"ENTITY":entity,"Sabra_Account":matrix,"Sabra":BPC_value,\
                                                     "P&L":PL_value,"Diff (Sabra-P&L)":diff,"Diff_Percent":diff_percent},index=[0])
                    diff_BPC_PL=pd.concat([diff_BPC_PL,diff_single_record],ignore_index=True)
                    
		    # for diff_detail_records
                    diff_detail_records=PL_with_detail.loc[(PL_with_detail["Sabra_Account"]==matrix)&(PL_with_detail["Entity"]==entity)]\
			                [["Entity","Sabra_Account","Tenant_Account",timeid]].rename(columns={timeid:"P&L Value"})
                    #if there is no record in diff_detail_records, means there is no mapping
                    if diff_detail_records.shape[0]==0:
                        diff_detail_records=pd.DataFrame({"Entity":entity,"Sabra_Account":matrix,"Tenant_Account":"Miss mapping accounts","Month":timeid,\
							"Sabra":BPC_value,"P&L Value":0,"Diff (Sabra-P&L)":diff},index=[0]) 
                    else:
                        diff_detail_records["Month"]=timeid
                        diff_detail_records["Sabra"]=BPC_value
                        diff_detail_records["Diff (Sabra-P&L)"]=diff

                    diff_BPC_PL_detail=pd.concat([diff_BPC_PL_detail,diff_detail_records])
    if diff_BPC_PL.shape[0]>0:
        percent_discrepancy_accounts=diff_BPC_PL.shape[0]/(BPC_Account.shape[0]*len(Total_PL.columns))
        diff_BPC_PL=diff_BPC_PL.merge(BPC_Account[["Category","Sabra_Account_Full_Name","BPC_Account_Name"]],left_on="Sabra_Account",right_on="BPC_Account_Name",how="left")        
        diff_BPC_PL=diff_BPC_PL.merge(entity_mapping[["Property_Name"]], on="ENTITY",how="left")
    else:
        percent_discrepancy_accounts=0
    return diff_BPC_PL,diff_BPC_PL_detail,percent_discrepancy_accounts
	

@st.cache_data(experimental_allow_widgets=True)
def View_Summary():
    global Total_PL
    def highlight_total(df):
        return ['color: blue']*len(df) if df.Sabra_Account.startswith("Total - ") else ''*len(df)
    def color_missing(data):
        return f'background-color: red'

    months=map(lambda x:x[4:6]+"/"+x[0:4],Total_PL.columns)
    m_str = ''
    for month in months:
        m_str += ", " + month
    st.write("Reporting months detected in P&L : "+m_str[1:])   
    st.write("The reporting month is "+latest_month[4:6]+"/"+latest_month[0:4])
    
    Total_PL.index=Total_PL.index.set_names(["ENTITY", "Sabra_Account"]) 
    Total_PL=Total_PL.fillna(0)
    latest_month_data=Total_PL[latest_month].reset_index(drop=False)
    latest_month_data=latest_month_data.merge(BPC_Account, left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")
    latest_month_data=latest_month_data.merge(entity_mapping[["Property_Name"]], on="ENTITY",how="left")

    missing_check=latest_month_data[["Property_Name","Category","ENTITY",latest_month]][latest_month_data["Category"].\
	    isin(['Revenue','Patient Days','Operating Expenses',"Facility Information","Balance Sheet"])].groupby(["Property_Name","Category","ENTITY"]).sum().reset_index(drop=False)
    missing_check=missing_check[missing_check[latest_month]==0]
	
    if missing_check.shape[0]>0:
        st.error("No data detected for below properties on specific accounts: ")
        col1,col2=st.columns([2,1])
        with col1:
            st.dataframe(missing_check[["Property_Name","Category",latest_month]].style.applymap(color_missing, subset=[latest_month]),
		    column_config={
			        "Property_Name": "Property",
			        "Category":"Sabra account-Total",
		                 latest_month:latest_month[4:6]+"/"+latest_month[0:4]},
			    hide_index=True)
        with col2:
            st.button("I'll fix and re-upload P&L")
            continue_run=st.button("Confirm and continue to run", on_click=clicked, args=["continue_button"]) 
            st.write("")#-----------------------write to error log-----------------------
        		    
        if not st.session_state.clicked["continue_button"]:
            st.stop()
		
    latest_month_data = latest_month_data.pivot(index=["Sabra_Account_Full_Name","Category"], columns="Property_Name", values=latest_month)
    latest_month_data.reset_index(drop=False,inplace=True)

    latest_month_data.rename(columns={"Sabra_Account_Full_Name":"Sabra_Account"},inplace=True) 
    latest_month_data=latest_month_data[latest_month_data["Sabra_Account"]==latest_month_data["Sabra_Account"]]	
	
    sorter=["Facility Information","Patient Days","Revenue","Operating Expenses","Non-Operating Expenses","Labor Expenses","Management Fee","Balance Sheet","Additional Statistical Information","Government Funds"]
    sorter=list(filter(lambda x:x in latest_month_data["Category"].unique(),sorter))
    latest_month_data.Category = latest_month_data.Category.astype("category")
    latest_month_data.Category = latest_month_data.Category.cat.set_categories(sorter)
    latest_month_data=latest_month_data.sort_values(["Category"]) 
	
    latest_month_data = (pd.concat([latest_month_data.groupby(by='Category',as_index=False).sum().\
                       assign(Sabra_Account="Total_Sabra"),latest_month_data]).\
                         sort_values(by='Category', kind='stable', ignore_index=True)[latest_month_data.columns])
     
    set_empty=list(latest_month_data.columns)
    set_empty.remove("Category")
    set_empty.remove("Sabra_Account")
    for i in range(latest_month_data.shape[0]):
        if latest_month_data.loc[i,"Sabra_Account"]=="Total_Sabra":
            latest_month_data.loc[i,"Sabra_Account"]="Total - "+latest_month_data.loc[i,'Category']
            if latest_month_data.loc[i,'Category'] =="Facility Information" or latest_month_data.loc[i,'Category'] =="Additional Statistical Information":
                latest_month_data.loc[i,set_empty]="  "
    entity_columns=latest_month_data.drop(["Sabra_Account","Category"],axis=1).columns	
    if len(latest_month_data.columns)>3:  # if there are more than one property, add total column
        latest_month_data["Total"] = latest_month_data[entity_columns].sum(axis=1)
        latest_month_data=latest_month_data[["Sabra_Account","Total"]+list(entity_columns)]
    else:
        latest_month_data=latest_month_data[["Sabra_Account"]+list(entity_columns)]
    
    st.markdown("{} {}/{} reporting data:".format(operator,latest_month[4:6],latest_month[0:4]))      
    st.markdown(latest_month_data.style.set_table_styles(styles).apply(highlight_total,axis=1).map(left_align)
		.format(precision=0,thousands=",").hide(axis="index").to_html(),unsafe_allow_html=True)
    st.write("")
	
    # upload latest month data to AWS
    col1,col2=st.columns([2,3])
    with col1:
        download_report(latest_month_data,"{} {}-{} Reporting".format(operator,latest_month[4:6],latest_month[0:4]))
    with col2:	
        submit_latest_month=st.button("Confirm and upload {} {}-{} reporting".format(operator,latest_month[4:6],latest_month[0:4]))
    upload_latest_month=Total_PL[latest_month].reset_index(drop=False)
    upload_latest_month["TIME"]=latest_month
    upload_latest_month=upload_latest_month.rename(columns={latest_month:"Amount"})
    upload_latest_month["EPM_Formula"]=None      # None EPM_Formula means the data is not uploaded yet
    upload_latest_month["Latest_Upload_Time"]=str(date.today())+" "+datetime.now().strftime("%H:%M")
    upload_latest_month["Operator"]=operator
    if submit_latest_month:
        # save tenant P&L to S3
	Upload_to_Onedrive(uploaded_finance,"test.xlsx")
        if not Upload_File_toS3(uploaded_finance,bucket_PL,"{}/{}_P&L_{}-{}.xlsx".format(operator,operator,latest_month[4:6],latest_month[0:4])):
                st.write(" ")  #----------record into error report------------------------	
                #Upload_to_Onedrive(uploaded_finance,"{}/{}_P&L_{}-{}.xlsx".format(operator,operator,latest_month[4:6],latest_month[0:4]))

        if BS_separate_excel=="Y":
            if not Upload_File_toS3(uploaded_BS,bucket_PL,"{}/{}_BS_{}-{}.xlsx".format(operator,operator,latest_month[4:6],latest_month[0:4])):
                st.write(" ")  #----------record into error report------------------------	
            #Upload_to_Onedrive(uploaded_BS,"{}/{}_BS_{}-{}.xlsx".format(operator,operator,latest_month[4:6],latest_month[0:4])) 
        if Update_File_inS3(bucket_PL,monthly_reporting_path,upload_latest_month,operator): 
            st.success("{} {} reporting data was uploaded to Sabra system successfully!".format(operator,latest_month[4:6]+"/"+latest_month[0:4]))
            
        else:
            st.write(" ")  #----------record into error report------------------------	
    else:
        st.stop()
    
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

def View_Discrepancy_Detail():
    global diff_BPC_PL,diff_BPC_PL_detail,Total_PL_detail,Total_PL
    # Sabra detail accounts mapping table
    def color_coding(row):
    	return ['color: blue'] * len(row) if row.Tenant_Account == " Total" else ['color: black'] * len(row)
    
    @st.cache_data	    
    def Diff_Detail_Process(diff_BPC_PL_detail):	    
        st.markdown("---")
        st.markdown("P&L—Sabra detail accounts mapping (for discrepancy data)") 
        diff_BPC_PL_detail = (pd.concat([diff_BPC_PL_detail.groupby(["Entity","Sabra_Account","Month","Sabra","Diff (Sabra-P&L)"], as_index=False).sum()
                      .assign(Tenant_Account=" Total"),diff_BPC_PL_detail]).sort_values(by=["Entity","Sabra_Account","Month","Sabra","Diff (Sabra-P&L)"], kind='stable', ignore_index=True)[diff_BPC_PL_detail.columns])
        diff_BPC_PL_detail=diff_BPC_PL_detail.merge(BPC_Account[["BPC_Account_Name","Sabra_Account_Full_Name"]],left_on="Sabra_Account", right_on="BPC_Account_Name",how="left")
        diff_BPC_PL_detail=diff_BPC_PL_detail.merge(entity_mapping[["Property_Name"]],left_on="Entity", right_on="ENTITY",how="left")
        diff_BPC_PL_detail=diff_BPC_PL_detail[["Property_Name","Month","Sabra_Account_Full_Name","Tenant_Account","Sabra","P&L Value","Diff (Sabra-P&L)"]].\
			rename(columns={"Property_Name":"Property","Sabra_Account_Full_Name":"Sabra Account"})
        return diff_BPC_PL_detail
    if diff_BPC_PL.shape[0]>0:      
        diff_BPC_PL_detail=Diff_Detail_Process(diff_BPC_PL_detail)    # format it to display
        diff_BPC_PL_detail_for_download=diff_BPC_PL_detail.copy()
        
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
        col1,col2=st.columns([1,3])
        with col1:
            download_report(Total_PL_detail.reset_index(drop=False),"Full mapping_{}".format(operator))
        with col2:
            download_report(diff_BPC_PL_detail_for_download,"accounts mapping for discrepancy_{}".format(operator))

# don't use cache
def View_Discrepancy(percent_discrepancy_accounts): 
    global diff_BPC_PL
    edited_diff_BPC_PL=diff_BPC_PL[diff_BPC_PL["Diff_Percent"]>10] 
	
    if percent_discrepancy_accounts>0:
        # save all the discrepancy 
        diff_BPC_PL["Operator"]=operator
        diff_BPC_PL=diff_BPC_PL.merge(entity_mapping[["GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE"]],on="ENTITY",how="left")
	# insert dims to diff_BPC_PL
        diff_BPC_PL["TIME"]=diff_BPC_PL["TIME"].apply(lambda x: "{}.{}".format(str(x)[0:4],month_abbr[int(str(x)[4:6])]))
        Update_File_inS3(bucket_PL,discrepancy_path,diff_BPC_PL,operator,"P&L")

	# only display the big discrepancy
        edited_diff_BPC_PL=diff_BPC_PL[diff_BPC_PL["Diff_Percent"]>10] 
        if edited_diff_BPC_PL.shape[0]>0:
            st.error("{0:.1f}% P&L data doesn't tie to Sabra data.  Please leave comments for discrepancy in below table.".format(percent_discrepancy_accounts*100))
            edited_diff_BPC_PL["Type comments below"]=""
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
	       
            col1,col2,col3=st.columns([2,2,4]) 
            with col1:                        
                download_report(edited_diff_BPC_PL[["Property_Name","TIME","Category","Sabra_Account_Full_Name","Sabra","P&L","Diff (Sabra-P&L)","Type comments below"]],"discrepancy_{}".format(operator))
        
            with col2:    
                submit_com=st.button("Submit comments")
            if submit_com:
                with st.empty():
                    with col3:
                        st.markdown("✔️ :green[Comments uploaded]")
                        st.write(" ")
                    # insert comments to diff_BPC_PL
                    diff_BPC_PL=pd.merge(diff_BPC_PL,edited_diff_BPC_PL[["Property_Name","TIME","Sabra_Account_Full_Name","Type comments below"]],on=["Property_Name","TIME","Sabra_Account_Full_Name"],how="left")
                    Update_File_inS3(bucket_PL,discrepancy_path,diff_BPC_PL,operator,"P&L")
            View_Discrepancy_Detail()
        else:
            st.success("All previous data in P&L ties with Sabra data")
    else:
            st.success("All previous data in P&L ties with Sabra data")
   
@st.cache_data(experimental_allow_widgets=True)        
def Read_Clean_PL(entity_i,sheet_type,PL_sheet_list,uploaded_file):  
    global latest_month,account_mapping
    sheet_name=str(entity_mapping.loc[entity_i,sheet_type])
    
    # read data from uploaded file
    count=0
    while(True):
        try:
            PL = pd.read_excel(uploaded_file,sheet_name=sheet_name,header=None)
            break
        except:
            col1,col2=st.columns(2) 
            with col1: 
                if sheet_type=="Sheet_Name_Finance":  
                    st.warning("Please provide sheet name of P&L data for property {}. ".format(entity_mapping.loc[entity_i,"Property_Name"]))
                elif sheet_type=="Sheet_Name_Occupancy":
                    st.warning("Please provide sheet name of Occupancy data for property {}. ".format(entity_mapping.loc[entity_i,"Property_Name"]))
                elif sheet_type=="Sheet_Name_Balance_Sheet":
                    st.warning("Please provide sheet name of Balance Sheet data in for property {}. ".format(entity_mapping.loc[entity_i,"Property_Name"]))
		    
            if len(PL_sheet_list)>0:
                with st.form(key=str(count)):                
                    sheet_name=st.selectbox(entity_mapping.loc[entity_i,"Property_Name"],[""]+PL_sheet_list)
                    submitted = st.form_submit_button("Submit")
                    count+=1
            else:
                with st.form(key=str(count)):     
                    sheet_name = st.text_input(entity_mapping.loc[entity_i,"Property_Name"])
                    submitted = st.form_submit_button("Submit")
                    count+=1
            if submitted:   
                continue
            else:
                st.stop()
		    
    if count>0:
        # update sheet name in entity_mapping
        entity_mapping.loc[entity_i,sheet_type]=sheet_name  
        # update entity_mapping in S3     
        Update_File_inS3(bucket_mapping,entity_mapping_filename,entity_mapping,operator)    

    # Start checking process
    with st.spinner("********Start to check property—'"+property_name+"' in sheet '"+sheet_name+"'********"):
        tenantAccount_col_no=Identify_Tenant_Account_Col(PL,sheet_name,sheet_type)
        if tenantAccount_col_no==None:
            st.error("Fail to identify tenant account column in sheet '{}'".format(sheet_name))
            st.stop()    
        date_header=Identify_Month_Row(PL,tenantAccount_col_no,sheet_name)
  
        if len(date_header[0])==1 and date_header[0]==[0]:
            st.error("Fail to identify month/year header in sheet '{}', please add it and re-upload.".format(sheet_name))
            st.stop()     
        PL.columns=date_header[0]

        #set tenant_account as index of PL
        PL=PL.set_index(PL.iloc[:,tenantAccount_col_no].values)
	
        #remove row above date row and remove column without date col name
        PL=PL.iloc[date_header[1]+1:,PL.columns!='0']
    
        #remove rows with nan tenant account
        nan_index=list(filter(lambda x:x=="nan" or x=="" or x==" " or x!=x ,PL.index))
        PL.drop(nan_index, inplace=True)
        #set index as str ,strip
        PL.index=map(lambda x:str(x).strip(),PL.index)
        PL=PL.map(lambda x: 0 if (x!=x) or (type(x)==str) or x==" " else x)
        # remove columns with all nan/0
        PL=PL.loc[:,(PL!= 0).any(axis=0)]
        # remove rows with all nan/0 value
        PL=PL.loc[(PL!= 0).any(axis=1),:]

        # mapping new tenant accounts
        new_tenant_account_list=list(filter(lambda x:x.upper().strip() not in list(account_mapping["Tenant_Formated_Account"]),PL.index))
            
        if len(new_tenant_account_list)>0:
            st.warning("Please complete mapping for below P&L accounts:")
            for i in range(len(new_tenant_account_list)):
                st.markdown("## Map **'{}'** to Sabra account".format(new_tenant_account_list[i])) 
                Sabra_main_account_value,Sabra_second_account_value=Manage_Account_Mapping(new_tenant_account_list[i])
                #insert new record to the bottom line of account_mapping
                new_mapping_row=[operator,Sabra_main_account_value,Sabra_second_account_value,new_tenant_account_list[i],new_tenant_account_list[i].upper(),"N"]            
                account_mapping=pd.concat([account_mapping, pd.DataFrame([new_mapping_row],columns=account_mapping.columns)],ignore_index=True)
            Update_File_inS3(bucket_mapping,account_mapping_filename,account_mapping,operator) 
            
            #if there are duplicated accounts in P&L, ask for confirming
            dup_tenant_account=set([x for x in PL.index if list(PL.index).count(x) > 1])
            if len(dup_tenant_account)>0:
                for dup in dup_tenant_account:
                    if dup.upper() not in list(account_mapping[account_mapping["Sabra_Account"]=="NO NEED TO MAP"]["Tenant_Formated_Account"]):
                        st.warning("Warning: There are more than one '{}' accounts in sheet '{}'. They will be summed up by default.".format(dup,sheet_name))
        
        # Map PL accounts and Sabra account
        PL,PL_with_detail=Map_PL_Sabra(PL,entity_i)  
    return PL,PL_with_detail
	
@st.cache_data(experimental_allow_widgets=True) 
def Check_Reporting_Month(PL):	
    latest_month=str(max(list(PL.columns)))
    col4,col5,col6=st.columns([5,1,8])
    with col4:  
        st.warning("The reporting month is: {}/{}. Is it true?".format(latest_month[4:6],latest_month[0:4])) 
    with col5:		
        st.button('Yes', on_click=clicked, args=["yes_button"])         
    with col6:
        st.button("No", on_click=clicked, args=["no_button"])       
    if st.session_state.clicked["yes_button"]:
        return latest_month
    elif st.session_state.clicked["no_button"]:
        with st.form("latest_month"):
            st.write("Please select reporting month:" )  
            col3,col4=st.columns(2)
            with col3:
                year = st.selectbox('Year', range(2023, date.today().year+1))
            with col4:
                month = st.selectbox('Month', range(1, 13),index=date.today().month-2)
            confirm_month=st.form_submit_button("Submit")
        if confirm_month:
            if month<10:
                latest_month=str(year)+"0"+str(month)
            else:
                latest_month=str(year)+str(month)
            return latest_month
        else:
            st.stop()
    else:
        st.stop()

@st.cache_data(experimental_allow_widgets=True)  
def Upload_And_Process(uploaded_file,file_type):
    global latest_month,property_name  # property_name is currently processed entity
    if True:
        if uploaded_file.name[-5:]=='.xlsx':
            PL_sheet_list=load_workbook(uploaded_file).sheetnames
           
        else:
            PL_sheet_list=[]
		
        Total_PL=pd.DataFrame()
        Total_PL_detail=pd.DataFrame()
 
        for entity_i in entity_mapping.index:   # entity_i is the entity code for each property
            if entity_mapping.loc[entity_i,"Property_in_separate_sheets"]=="Y":
                sheet_name_finance=str(entity_mapping.loc[entity_i,"Sheet_Name_Finance"])
                sheet_name_occupancy=str(entity_mapping.loc[entity_i,"Sheet_Name_Occupancy"])
                sheet_name_balance=str(entity_mapping.loc[entity_i,"Sheet_Name_Balance_Sheet"])
                property_name=str(entity_mapping.loc[entity_i,"Property_Name"])

		# ****Finance and BS in one excel****
                if file_type=="Finance" and BS_separate_excel=="N": 
                    PL,PL_with_detail=Read_Clean_PL(entity_i,"Sheet_Name_Finance",PL_sheet_list,uploaded_file)
		    
                    # check if census data in another sheet
                    if sheet_name_occupancy!='nan' and sheet_name_occupancy==sheet_name_occupancy and sheet_name_occupancy!="" and sheet_name_occupancy!=" "\
                    and sheet_name_occupancy!=sheet_name_finance:
                        PL_occ,PL_with_detail_occ=Read_Clean_PL(entity_i,"Sheet_Name_Occupancy",PL_sheet_list,uploaded_file) 
                        PL=PL.combine_first(PL_occ)
                        PL_with_detail=PL_with_detail.combine_first(PL_with_detail_occ)
		
		    # check if balance sheet data existed   
                    if sheet_name_balance!='nan' and sheet_name_balance==sheet_name_balance and sheet_name_balance!="" and sheet_name_balance!=" " and sheet_name_balance!=sheet_name_finance:
                        PL_BS,PL_with_detail_BS=Read_Clean_PL(entity_i,"Sheet_Name_Balance_Sheet",PL_sheet_list,uploaded_file)
                        PL=PL.combine_first(PL_BS)
                        PL_with_detail=PL_with_detail.combine_first(PL_with_detail_BS)
                elif file_type=="Finance" and BS_separate_excel=="Y": 
                    PL,PL_with_detail=Read_Clean_PL(entity_i,"Sheet_Name_Finance",PL_sheet_list,uploaded_file)
                elif file_type=="BS" and BS_separate_excel=="Y": 
                    PL,PL_with_detail=Read_Clean_PL(entity_i,"Sheet_Name_Balance_Sheet",PL_sheet_list,uploaded_file)
            Total_PL=pd.concat([Total_PL,PL], ignore_index=False, sort=False)
            Total_PL_detail=pd.concat([Total_PL_detail,PL_with_detail], ignore_index=False, sort=False)
            #st.success("Property {} checked.".format(entity_mapping.loc[entity_i,"Property_Name"]))
    return Total_PL,Total_PL_detail

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
if 'clicked' not in st.session_state:
    st.session_state.clicked = {"yes_button":False,"no_button":False,"forgot_password_button":False,"forgot_username_button":False,"continue_button":False}

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
    BPC_pull,month_dic,year_dic=Initial_Paramaters(operator)
    entity_mapping,account_mapping=Initial_Mapping(operator)
  
    menu=["Upload P&L","Manage Mapping","Instructions","Edit Account","Logout"]
    choice=st.sidebar.selectbox("Menu", menu)
    if choice=="Upload P&L":
        global latest_month
        latest_month='2023'
        if all(entity_mapping["BS_separate_excel"]=="Y"):
            BS_separate_excel="Y"
        else:
            BS_separate_excel="N"

        with st.form("upload_form", clear_on_submit=True):
            col1,col2=st.columns(2)
            with col1:
                st.subheader("Upload P&L:")
                uploaded_finance=st.file_uploader(":star: :red[XLSX recommended] :star:",type={"xlsx","xlsm","xls"},accept_multiple_files=False,key="Finance_upload")
                
            with col2:
                if BS_separate_excel=="Y":
                    st.subheader("Upload Balance Sheet:")
                    uploaded_BS=st.file_uploader("",type={"xlsx","xlsm","xls"},accept_multiple_files=False,key="BS_upload")
            submitted = st.form_submit_button("Upload")
        if submitted:
	    # clear cache for every upload
            st.cache_data.clear()
            st.cache_resource.clear()
            st.session_state.clicked = {"yes_button":False,"no_button":False,"forgot_password_button":False,"forgot_username_button":False,"continue_button":False}
        if uploaded_finance:
            with col1:
                st.markdown("✔️ :green[P&L selected]")
        else:
            st.write("P&L wasn't upload.")
            st.stop()
 
	    
        if BS_separate_excel=="Y" and uploaded_BS:
            with col2:
                st.markdown("✔️ :green[Balance sheet selected]")

        elif BS_separate_excel=="Y" and not uploaded_BS:
            st.write("Balance sheet wasn't upload.")
            st.stop()
        if BS_separate_excel=="N":  # Finance/BS are in one excel
            with st.spinner('Wait for P&L process'):
                Total_PL,Total_PL_detail=Upload_And_Process(uploaded_finance,"Finance")
        elif BS_separate_excel=="Y":     # Finance/BS are in different excel  
            # process Finance 
            with st.spinner('Wait for P&L process'):
                Total_PL,Total_PL_detail=Upload_And_Process(uploaded_finance,"Finance")
		# process BS 
                Total_BL,Total_BL_detail=Upload_And_Process(uploaded_BS,"BS")
            
	    # combine Finance and BS
            Total_PL=Total_PL.combine_first(Total_BL)
            Total_PL_detail=Total_PL_detail.combine_first(Total_BL_detail)
        
        with st.spinner('Wait for data checking'):    
            latest_month=Check_Reporting_Month(Total_PL)  
            previous_month_list=[month for month in Total_PL.columns.sort_values() if month<latest_month]
            if len(previous_month_list)>0:   # there are previous months in P&L
                diff_BPC_PL,diff_BPC_PL_detail,percent_discrepancy_accounts=Compare_PL_Sabra(Total_PL,Total_PL_detail,latest_month,previous_month_list)

	# 1 Summary
        with st.expander("Summary of P&L" ,expanded=True):
            ChangeWidgetFontSize('Summary of P&L', '25px')
            View_Summary()
      
        # 2 Discrepancy of Historic Data
        with st.expander("Discrepancy for Historic Data",expanded=True):
            ChangeWidgetFontSize('Discrepancy for Historic Data', '25px')
            if len(previous_month_list)>0:		
                View_Discrepancy(percent_discrepancy_accounts)
                
            else:
                st.write("There is no previous month data in tenant P&L")
    elif choice=="Manage Mapping":
        with st.expander("Manage Property Mapping" ,expanded=True):
            ChangeWidgetFontSize('Manage Property Mapping', '25px')
            entity_mapping=Manage_Entity_Mapping(operator)
        with st.expander("Manage Account Mapping",expanded=True):
            ChangeWidgetFontSize('Manage Account Mapping', '25px')
            col1,col2=st.columns(2)
            with col1:
                new_tenant_account=st.text_input("Enter new tenant account and press enter to apply. If there are multiple accounts mapping to the same Sabra account, use commas to separate them. For example: Revenue_A,Revenue_B,Revenue_C")
                
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
                    st.markdown("## Map **'{}'** to Sabra account".format(",".join(new_tenant_account_list))) 
                    Sabra_main_account_value,Sabra_second_account_value=Manage_Account_Mapping(",".join(new_tenant_account_list))
                    
                    if len(new_tenant_account_list)>1:  # there is a list of new tenant accounts mapping to one sabra account   
                        new_row=[]
                        for account_i in range(len(new_tenant_account_list)):
                            new_row.append([operator,Sabra_main_account_value,Sabra_second_account_value,new_tenant_account_list[account_i],new_tenant_account_list[account_i].upper(),"N"])
                        new_accounts_df = pd.DataFrame(new_row, columns=account_mapping.columns)

                        #insert new records to the bottom line of account_mapping one by one
                        account_mapping = pd.concat([account_mapping, new_accounts_df], ignore_index=True)

                    elif len(new_tenant_account_list)==1:
	                #insert new record to the bottom line of account_mapping
                        account_mapping.loc[len(account_mapping.index)]=[operator,Sabra_main_account_value,Sabra_second_account_value,new_tenant_account_list[0],new_tenant_account_list[0].upper(),"N"]   
                    Update_File_inS3(bucket_mapping,account_mapping_filename,account_mapping,operator)
			
    elif choice=='Instructions':
        # insert Video
        video=s3.get_object(Bucket=bucket_mapping, Key="Sabra App video.mp4")
        st.video(BytesIO(video['Body'].read()), format="mp4", start_time=0)
	    
    elif choice=="Edit Account": 
	# update user details widget
        try:
            authenticator.update_user_details(st.session_state["username"], 'Update user details',config)
            #if authenticator.update_user_details(st.session_state["username"], 'Update user details'):
                #s33 = boto3.resource("s3").Bucket(bucket_PL)
                #json.dump_s3 = lambda obj, f: s33.Object(key=f).put(Body=json.dumps(obj))
                #json.dump_s3(config, "config.yaml") # saves json to s3://bucket/key
        except Exception as e:
            st.error(e)

    elif choice=="Logout":
        authenticator.logout('Logout', 'main')



# ----------------for Sabra account--------------------	    
elif st.session_state["authentication_status"] and st.session_state["operator"]=="Sabra":
    operator_list=Read_CSV_FromS3(bucket_mapping,operator_list_path)
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
            account_mapping =Read_CSV_FromS3(bucket_mapping, account_mapping_filename)
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
                        if Save_CSV_ToS3(account_mapping,bucket_mapping, account_mapping_filename):           
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
            data_obj =s3.get_object(Bucket=bucket_PL, Key=monthly_reporting_path)

            if int(data_obj["ContentLength"])<=2:  # empty file
                st.success("there is no un-uploaded data")
            else:
                data=pd.read_csv(BytesIO(data_obj['Body'].read()),header=0)
                data=data[list(filter(lambda x:"Unnamed" not in x and 'index' not in x ,data.columns))]
                data["Upload_Check"]=""
                # summary for operator upload
                data["TIME"]=data["TIME"].apply(lambda x: "{}.{}".format(str(x)[0:4],month_abbr[int(str(x)[4:6])]))
                col1,col2,col3=st.columns((3,1,1))
                summary=data[["TIME","Operator","Latest_Upload_Time"]].drop_duplicates()
                with col2:
                    data=filters_widgets(data,["Operator","TIME"],"Horizontal")
                with col1:
                    st.dataframe(
			    summary,
			    column_config={
			        "TIME": "Reporting month",
			        "Latest_Upload_Time":"Latest submit"},
			    hide_index=True)
                st.write("")
                st.subheader("Download reporting data")    
		    
                # add average column for each line , average is from BPC_pull
                BPC_pull=Read_CSV_FromS3(bucket_mapping,BPC_pull_filename)
                BPC_pull.columns=list(map(lambda x :str(x) if x!="ACCOUNT" else "Sabra_Account", BPC_pull.columns))
                data=data.merge(BPC_pull[["ENTITY","Sabra_Account","mean"]], on=["ENTITY","Sabra_Account"],how="left")	
		# add "GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE" from entity_mapping
                entity_mapping=Read_CSV_FromS3(bucket_mapping,entity_mapping_filename)
                data=data.merge(entity_mapping[["ENTITY","GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE"]],on="ENTITY",how="left")

                data=EPM_Formula(data,"Amount")	
                download_file=data.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download reporting data",data=download_file,file_name="Operator reporting data.csv",mime="text/csv")
