#!/usr/bin/python3
# -*- coding:utf-8 -*-

# python3.5
from urllib import request, parse
import json
import pymysql
from datetime import datetime
from functools import reduce
import jieba.analyse

class SCK(object):
    def __init__(self,Name='None'):
        #新闻频道
        if(Name != 'None'):
            self.ChineseChannelName = Name
        else:
            print('The name of the channel is wrong!')
        #统计每次插入数据库中的数据条数
        self.InsertCount = self.DownloadCount = 0

        db = pymysql.connect(host="127.0.0.1",port=3306,user="root",passwd="123456",db="news",charset='utf8')
        cursor = db.cursor()
        #由中文频道名找到英文频道名
        sql = 'SELECT channelId,english_name FROM channellist where name="%s最新"' % (self.ChineseChannelName)
        try:
            cursor.execute(sql)
            results = cursor.fetchone()
            self.channelId = results[0]
            self.EnglsihChannelName = results[1]
        except Exception as e:
            print(e)
        db.close()


    def extract_tags(self,content):
        exclude = set([u'记者', u'新闻', u'报', u'本报', u'月', u'日', u'开始', u'觉得', u'起来',
                            u'大家', u'知道', u'可能', u'感觉',u'见到', u'没有', u'出来', u'跟着',
                        u'球员', u'球队', u'比赛', u'感觉', u'见到', u'没有', u'出来',
                       u'跟着'])
        res = []
        for key, weight in jieba.analyse.extract_tags(content, topK=None, withWeight=True):
            if key in exclude:
                continue
            res.append((key, weight))
        return res

    def combineAllNewsItems(self,str_list):
        result = reduce(lambda ns1, ns2: ns1 + '\n\n' + ns2, str_list)
        return result

    def DownloadNewsdata(self):
            print('send data....')
            showapi_appid = "53310"
            showapi_sign = "af66291753d249c495eb41bbc41793eb"
            url = "http://route.showapi.com/109-35"
            send_data = parse.urlencode([
                ('showapi_appid', showapi_appid)
                , ('showapi_sign', showapi_sign)
                , ('channelId', self.channelId)
                , ('channelName', "")
                , ('title', "")
                #修改页面
                , ('page', "%d"%(self.page))
                , ('needContent', "1")
                , ('needHtml', "")
                , ('needAllList', "")
                , ('maxResult', "60")
                , ('id', "")
            ])

            print('now page:',self.page)
            req = request.Request(url)
            try:
                response = request.urlopen(req, data=send_data.encode('utf-8'), timeout=10)  # 10秒超时反馈
            except Exception as e:
                print(e)
            result = response.read().decode('utf-8')
            result_json = json.loads(result)

            with open('temp_contentlist.json', 'w', encoding='utf-8') as json_file:
                json.dump(result_json, json_file, ensure_ascii=False)

    def LoadNewsdata(self):
        with open('temp_contentlist.json', 'r', encoding='utf-8') as json_file:
            result_json = json.load(json_file)
        return result_json

    def MysqlInsert(self,newsdata):
        db = pymysql.connect(host="127.0.0.1",port=3306,user="root",passwd="123456",db="news",charset='utf8')
        cursor = db.cursor()
        for NewsDict in newsdata['showapi_res_body']['pagebean']['contentlist']:
            content = NewsDict['content']
            id = NewsDict['id']
            pubDate = NewsDict['pubDate']
            channelName = NewsDict['channelName']
            title = NewsDict['title']
            desc = NewsDict['desc']
            if NewsDict['havePic'] == True:
                imageurls = NewsDict['imageurls'][0]['url']
            else:
                imageurls = 'None'
            source = NewsDict['source']
            link = NewsDict['link']

            sql = 'insert into contentlist_%s value ("%s","%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s")' % \
                      (self.EnglsihChannelName, content, id, pubDate, channelName, title, desc, imageurls, source, link)
            self.DownloadCount += 1

            try:
                cursor.execute(sql)
                db.commit()
                self.InsertCount += 1
            except Exception as e:
                print (e)
        db.close()

    def MysqlRead(self):
        db = pymysql.connect(host="127.0.0.1",port=3306,user="root",passwd="123456",db="news",charset='utf8')
        cursor = db.cursor()
        #按时间先后排序读取，时间越近越先
        sql = 'SELECT content FROM contentlist_%s order by pubDate desc' % (self.EnglsihChannelName)
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return results
        except:
            print("Error: unable to fetch data")
        db.close()

    def run(self):
        self.page=1
        self.DownloadNewsdata()
        #读取存在本地临时json中的数据
        newsdata=self.LoadNewsdata()
        #将数据插入数据库中
        self.MysqlInsert(newsdata)
        allpages = int(newsdata['showapi_res_body']['pagebean']['allPages'])

        if(allpages > 1):
            for self.page in range(2,allpages+1):
                #下载原始数据
                self.DownloadNewsdata()
                #读取存在本地临时json中的数据
                newsdata=self.LoadNewsdata()
                #将数据插入数据库中
                self.MysqlInsert(newsdata)

        starttime = datetime.now()

        news_str_list=[]
        '''waitlist = ['automobile','cba','computer','digital','education','entertainment',
                    'game','international_football','internet','national','science','sexual_relationship',
                    'taiwan','woman']
        '''
        sqlRead_results = self.MysqlRead()
        #将从数据库中提取出来的str组成list
        for i in range(0,len(sqlRead_results)):
            news_str_list.append(sqlRead_results[i][0])
        #type=str
        combine_result = self.combineAllNewsItems(news_str_list)
        extract_result = self.extract_tags(combine_result)
        for i in range(0,10):
            print(extract_result[i])
        print('Come from:%s, search time:' % (self.ChineseChannelName),datetime.now())

        closetime=datetime.now()
        deltime = closetime-starttime
        print('='*50)
        print('共有 %d 字， 耗时' % (len(combine_result)),deltime)
        print("下载:",self.DownloadCount,' 条数据， ','成功插入：',self.InsertCount,' 条数据')
