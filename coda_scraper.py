#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
import json
import google.oauth2.service_account
import google.auth #layer)
import gspread #(klayer)
from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
from gspread_dataframe import get_as_dataframe, set_with_dataframe

token_ = ##insert coda api token here##

headers = {'Authorization': 'Bearer f{token_}'}
uri = 'https://coda.io/apis/v1/docs'
params = {
      'isOwner': True
    }
res = requests.get(uri, headers=headers, params=params).json()

##test to get name of doc. once found the desired name of doc, will use res['href'] for uri variable
# print(f'First doc is: {res["items"][0]["name"]}')


uri = res['href'].split('/canvas-')[0]
pages_res = requests.get(uri, headers=headers).json()

##test to get name of page and confirm in coda UI. 
print(f'The name of the first page is {pages_res["items"][0]["name"]}')

## add input for user to select which month they want to run report. 
month_to_run = input("What month are you looking ro review? : ")

##get page_ids for each week in the month...Month is this particular use case but would be any subpage within the parent page, in this case month_to_run
sm = [x for x in pages_res['items'] if x['name'] == month_to_run][0]['children'] ##sm = selected_month
week_res = requests.get(sm[3]['href'], headers=headers).json()



###looping through subpages to scrape data and set dataframe ### 
master_df = pd.DataFrame()

for week_ in sm:
    week_res = requests.get(week_['href'], headers=headers).json()

#     week_res = week_
    for day in week_res['children']:
        if 'Day' in day['name']:
            day_res = requests.get(day['href'], headers=headers).json()
            print(day['href'])

            ##generating the html content from coda page

            payload = {'outputFormat': 'html'}
            req = requests.post(day['href']+'/export', headers=headers, json=payload)
            req.raise_for_status() # Throw if there was an error.
            res = req.json()
            time.sleep(5)
            while res['status'] == 'inProgress':
                print(res['status'])
                time.sleep(3)
                res = requests.get(res["href"], headers=headers).json()
            print(f'Request status: {res["status"]}')

            # Download the HTML file
            html_response = requests.get(res['downloadLink'])
            html_content = html_response.content

            # Parse the HTML content
            soup = BeautifulSoup(html_content, 'html.parser')

            tickers = [x.text.strip() for x in soup.find_all('h3')]
            imgs = [x['src'] for x in soup.find_all('img')]

            if len(tickers) > 0:
                print(tickers)

                df = pd.DataFrame([tickers,imgs]).T
                df[[0,2]] = df[0].str.split(' ', n=1, expand = True)
                df.columns = ['ticker','chart','date']

                master_df = master_df.append(df)

        print("")

master_df = master_df[(~master_df['date'].isna()) & (master_df['date'] != 'Stock Here') & (~master_df['chart'].isna())]
master_df = master_df.reset_index(drop = True)
        
for index,row in master_df.iterrows():
    ticker = row['ticker']
    date = row['date'].replace('/','-')
    finviz_url = f'https://elite.finviz.com/quote.ashx?t={ticker}&p=i1&r=range_{date}x{date}'
    master_df.at[index,'finviz_chart'] = finviz_url
    
master_df['date'] = pd.to_datetime(master_df['date'].str.replace('- ','').str.replace('.',''))



### pushing table to googlesheets for review ## 

####accessing google credentials... 
with open('/credentials_file_path.json') as json_file:  ##insert file path to creds
    cs = json.load(json_file)

SCOPES=(['https://www.googleapis.com/auth/cloud-platform','https://www.googleapis.com/auth/spreadsheets'])
credentials = service_account.Credentials.from_service_account_info(cs, scopes=SCOPES)


sheet= ### insert google sheet url here that you want to drop dataframe to ### 
gs=gspread.authorize(credentials)
sh = gs.open_by_url(sheet)
worksheet = sh.worksheet('missed_trades')

###set filtered df to gsheets only if new data exists. Specify row as len of existing + 2 to append at bottom of list
if len(master_df) > 0:
    set_with_dataframe(worksheet,master_df,include_index=False,include_column_header=True,row=1)
else:
    print("no new data to add")

