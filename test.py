Skip to content
SabraHealthCare
/
test2

Type / to search

Code
Issues
Pull requests
Projects
Security
Insights
Settings
Commit
Update test.py
 main
@SabraHealthCare
SabraHealthCare committed 19 hours ago 
1 parent 4e4ab14
commit f8b2220
Showing 1 changed file with 1 addition and 1 deletion.
  2 changes: 1 addition & 1 deletion2  
test.py
@@ -662,67 +662,67 @@
                   
                    #if there is no record in diff_detail_records, means there is no mapping
                    if diff_detail_records.shape[0]==0:
                        diff_detail_records=pd.DataFrame({"Entity":entity,"Sabra_Account":matrix,"Tenant_Account":"Miss mapping accounts","Month":timeid,"Sabra":BPC_value,"Diff (Sabra-P&L)":diff,"P&L Value":0},index=[0])   
                    diff_BPC_PL_detail=pd.concat([diff_BPC_PL_detail,diff_detail_records])
    if diff_BPC_PL.shape[0]>0:
        percent_discrepancy_accounts=diff_BPC_PL.shape[0]/(BPC_Account.shape[0]*len(Total_PL.columns))
        diff_BPC_PL=diff_BPC_PL.merge(BPC_Account[["Category","Sabra_Account_Full_Name","BPC_Account_Name"]],left_on="Sabra_Account",right_on="BPC_Account_Name",how="left")        
        diff_BPC_PL=diff_BPC_PL.merge(entity_mapping[["Property_Name"]], on="ENTITY",how="left")
        diff_BPC_PL['Type comments below']=""
    else:
        percent_discrepancy_accounts=0
    return diff_BPC_PL,diff_BPC_PL_detail,percent_discrepancy_accounts
	
@st.cache_data(experimental_allow_widgets=True)
def View_Summary(uploaded_file):
    global Total_PL
    def highlight_total(df):
        return ['color: blue']*len(df) if df.Sabra_Account.startswith("Total - ") or df.Sabra_Account.startswith("Licensed Beds") or df.Sabra_Account.startswith("Operating Beds") else ''*len(df)
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
        st.error("No data detected for below accounts: ")
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

    st.write(latest_month_data)

    sorter=["Facility Information","Patient Days","Revenue","Operating Expenses","Non-Operating Expenses","Labor Expenses","Management Fee","Balance Sheet","Additional Statistical Information","Government Funds"]
    latest_month_data.Category = latest_month_data.Category.astype("category")
    latest_month_data.Category = latest_month_data.Category.cat.set_categories(sorter)
    latest_month_data=latest_month_data.sort_values(["Category"]) 
	
    latest_month_data = (pd.concat([latest_month_data.groupby(by='Category',as_index=False).sum().\
                       assign(Sabra_Account="Total_Sabra"),latest_month_data]).\
                         sort_values(by='Category', kind='stable', ignore_index=True)[latest_month_data.columns])
     
    
    for i in range(latest_month_data.shape[0]):
        if latest_month_data.loc[i,"Sabra_Account"]=="Total_Sabra" and latest_month_data.loc[i,'Category'] !="Facility Information":
            latest_month_data.loc[i,"Sabra_Account"]="Total - "+latest_month_data.loc[i,'Category']
    drop_facility_info_total=latest_month_data["Sabra_Account"] == 'Total_Sabra'
    latest_month_data=latest_month_data[~drop_facility_info_total]
	
    entity_columns=latest_month_data.drop(["Sabra_Account"],axis=1).columns	
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
    upload_latest_month=upload_latest_month.merge(entity_mapping[["Operator","GEOGRAPHY","LEASE_NAME","FACILITY_TYPE","INV_TYPE"]].reset_index(drop=False),on="ENTITY",how="left")
    upload_latest_month["TIME"]=latest_month
    upload_latest_month=upload_latest_month.rename(columns={latest_month:"Amount"})
    upload_latest_month["EPM_Formula"]=None      # None EPM_Formula means the data is not uploaded yet
    upload_latest_month["Latest_Upload_Time"]=str(date.today())+" "+datetime.now().strftime("%H:%M")
0 comments on commit f8b2220
@SabraHealthCare
Comment
 
Leave a comment
 
 You’re not receiving notifications from this thread.
Footer
© 2023 GitHub, Inc.
Footer navigation
Terms
Privacy
Security
Status
Docs
Contact
Update test.py · SabraHealthCare/test2@f8b2220
