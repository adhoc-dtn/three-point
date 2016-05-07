# -*- coding: utf-8 -*-
# python 3.4

import lxml.html
import JPX.data.toushin as ts
import JPX.data.kdb as kdb
import urllib.request
from datetime import datetime
from datetime import timedelta
import csv
import random
import time
import os.path
from urllib.request import urlopen
from bs4 import BeautifulSoup
import re

#日数取得期間
span = 40
#株数
tani_kabu = 100
#売買単位
tani_baibai = 1
#売買手数料(円)
tesuryo = 609


#ログファイル（取引結果)
logfile_kekka = 'torihiki.log'

#１社を対象にし，三点チャージ法で売買判断する
def threePointCharge(fundcode):
    #本日の日付と，span日前の日付を取得
    today   = datetime.today()
    day_old = today - timedelta(days=span)
    
    today_c = datetime(today.year, today.month, today.day)
    day_old_c = datetime(day_old.year,day_old.month,day_old.day)

    #netaの中に仕込む（過去分）
    neta = kdb.historical(fundcode, interval='d', start=day_old_c, end=today_c)
    
    #現在分を取得する
    genzai = getCurrentPrice(fundcode)

    # print(fundcode,"のネタです")
    #print(fundcode,"の現在価格です")
    #print(genzai)
    #print(fundcode,"のネタです")
    #print(neta)
    #ネタから乖離値・ボリュームレシオ．RSIを取得
    kairi = getKairi(neta,genzai)
    vr    = getVR(neta)
    rsi   = getRSI(neta)
    
    print ("→ [乖離値] : %5.2f " % kairi)
    print ("→ [VR]     : %5.2f " % vr)
    print ("→ [RSI]    : %5.2f"  % rsi)

#--------------------------------------------------------------------
    #売買判断する部分作る end
    if kairi<=-0.15 and vr <= 0.7 and rsi <= 0.25 :
        print ("[",fundcode,"] → 買いですな!")
        #買いメソッドを起動
        #buy(fundcode, int(neta.iloc[len(neta)-1][3]))
    elif kairi > 0.15 and (vr >= 2.5 or rsi >= 0.7):
        print ("[",fundcode,"] → 売りですな!")
        #売りメソッドを起動
        #sell(fundcode,int(neta.iloc[len(neta)-1][3]))
    else:
        print ("[",fundcode,"] → (状況変化なし)")
#        buy(fundcode, int(neta.iloc[len(neta)-1][3]))
#-------------------------------------------------------------------

#現在の値段の取得
def getCurrentPrice(code):
    code_trans= code.replace('-', '.') # ドットをハイフンに変換
    #print(code_trans)
    d = dict(code=code_trans)
    url = "http://stocks.finance.yahoo.co.jp/stocks/detail/?code={code}" .format(**d)
    
    html = urlopen(url)
    bsObj = BeautifulSoup(html)
    
    for neta in bsObj.findAll("td",{"class":"stoksPrice"}):
        price_tag = re.search(r'\d+',str(neta))
        if price_tag:
            price = int(price_tag.group())
            return price
    

#level1のメソッド群
#乖離値の取得
def getKairi(contents,genzai):
    goukei = genzai
    #データが入っている営業日のカウント
    count_data = 0
    #本日分の値がない場合，乖離なしとしてリターン
    if contents.iloc[len(contents)-1][3] in ["-"]:
        return 0
    
    for i in range(0, len(contents)-1, 1):
        if contents.iloc[i][3] not in ["-"]:
            goukei += int(contents.iloc[i][3])
            #print(goukei)
            count_data+=1

    #現在価格+過去の価格での平均値の算出
    average = float(goukei)/(1 + len(contents))
    #print(average)
    kairi  = (genzai - average)/average
    return kairi

def getVR(contents):
    plus     = 0
    minus    = 0
    nochange = 0
    
    for i in range(1, len(contents)-1, 1):
        #評価計算
        now = contents.iloc[i][3]
        if contents.iloc[i-1][3] in ["-"]:
            #計算見送り
            old = now
            #print(contents.iloc[i-1][3],"oldが-")
        elif contents.iloc[i][3] in ["-"]:
            #空回し 
            old = contents.iloc[i-1][3]
            #print(contents.iloc[i][3],"nowが-")

        else :
            old = contents.iloc[i-1][3]
            
            atai = int(now) - int(old)
            if   atai > 0:
                plus+= contents.iloc[i-1][4]
            elif atai < 0:
                minus+= abs(contents.iloc[i-1][4])
            else:
                nochange += contents.iloc[i-1][4]

            
        if float(minus)+float(nochange)/2 > 0:
            vr = (float(plus)+float(nochange)/2)/(float(minus)+float(nochange)/2)
        else:
            vr = 0
    return vr

def getRSI(contents):
    #上がり幅
    plus       = 0
    count_plus = 0
    #下がり幅
    minus      = 0
    count_minus= 0

    
    for i in range(1, len(contents)-1, 1):
        #評価計算
        now = contents.iloc[i][3]
        if contents.iloc[i-1][3] in ["-"]:
            #計算見送り
            old = now
            #print(contents.iloc[i-1][3],"oldが-")

        elif contents.iloc[i][3] in ["-"]:
            #空回し 
            old = contents.iloc[i-1][3]
            #print(contents.iloc[i][3],"nowが-")

        else :
            old = contents.iloc[i-1][3]
            atai = int(now) - int(old)

            if   atai > 0:
                plus       += atai
                count_plus += 1
            elif atai < 0:
                minus += abs(atai)
                count_minus+=1

        
    rsi = (float(plus)/count_plus) / (float(plus)/count_plus + float(minus)/count_minus)
    
    return rsi

#買いメソッド
def buy(fundcode, kakaku):
    kabusu_file  = open(fundcode, 'r')
    kabusu_str = kabusu_file.read()
    print (kabusu_str)
    kabusu = int(kabusu_str)
    kabusu_file.close()
    #取引処理#
    
    #ログの書き込み
    #株数の更新
    kabusu = kabusu + tani_kabu*tani_baibai
    kabusu_file  = open(fundcode, 'w')
    kabusu_file.write(str(kabusu))
    kabusu_file.close()
    #取引収支の記入
    today   = datetime.today().strftime("%y-%m-%d")
    syushi_file_name = '%s_%s' % (today, fundcode)
    #本日取引実施済の場合，履歴ファイルから更新を行う．
    if os.path.exists( syushi_file_name ) == True:
        syushi_file  = open(syushi_file_name, 'r')
        syushi = int(syushi_file.read())
        syushi_file.close()
    #本日お初の取引の場合
    else :
        syushi = 0
    #収支= 現在値-現在価格＊株数＊売買単位-手数料
    syushi = syushi - kakaku*tani_kabu*tani_baibai - tesuryo
    
    syushi_file  = open(syushi_file_name, 'w')
    syushi_file.write(str(syushi))
    syushi_file.close()

    
    
#売りメソッド
#def sell(fundcode, kakaku):


     
if __name__ == '__main__':
    # dictにパラメータを突っ込む

    codes_file  = open('code.csv', 'r')
    data = csv.reader(codes_file)
    count = 0
    
    # print("[",count,"]: CODE  9880評価開始")
    # args = dict(fundcode = '9880-T')
    # threePointCharge(**args)

    for row in data:
        print ("------------------------------------------")
        count = count + 1
        code_toString = '%s' % row[0]
        args = dict(fundcode = code_toString)
        #dictごと渡してアンパック
        randomv = random.uniform(0.4,5.6)
        #print(count, ": CODE ",row[0],"評価開始．（ランダムウェイト until ",randomv,"秒）")
        print("[",count,"]: CODE ",row[0],"評価開始")
        time.sleep(random.uniform(0.4,5.6))
        threePointCharge(**args)

    codes_file.close()
