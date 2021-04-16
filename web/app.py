from flask import (Flask, Blueprint, flash, g, redirect, render_template, request, session, url_for)
import socket
import redis
import functools
import requests
import threading
import time


def test_one(url, request_id):
	try:
		r = requests.get(url)
		if r.status_code == 200:
			cache.incr("test" + str(request_id) + "_OK")
		cache.incr("test" + str(request_id) + "_Hit")
	except:
		cache.incr("test" + str(request_id) + "_Miss")

def start_test(url, load, request_id, max_time):
	start_time = time.time()
	for i in range(load):
		time_passed = time.time() - start_time
		cache.set("test" + str(request_id) + "_time_passed", round(time_passed, 2))
		if time_passed > max_time:
			cache.set("test" + str(request_id) + "_processing", 'Finished')
			break
		x = threading.Thread(target=test_one, args=(url, request_id,))
		x.start()
		if i == load - 1:
			cache.set("test" + str(request_id) + "_processing", 'Finished')


app = Flask(__name__)
cache = redis.Redis(host='redis', port=6379)


@app.route('/', methods=['GET', 'POST'])
def index():
	if request.method == 'POST':
		url = request.form['url']
		load = request.form['load']
		max_time = request.form['time']
		try:
			r = requests.get(url)
		except:
			return redirect(url_for('error', id=1))
		try:
			load = int(load)
		except:
			return redirect(url_for('error', id=2))
		try:
			max_time = int(max_time)
		except:
			return redirect(url_for('error', id=3))	

		request_id = cache.incr('request_counter')
		pipe = cache.pipeline()
		pipe.set("test" + str(request_id) + "_url", url)
		pipe.set("test" + str(request_id) + "_load", load)
		pipe.set("test" + str(request_id) + "_time", max_time)
		pipe.set("test" + str(request_id) + "_processing", 'Processing')
		pipe.execute()
		return redirect(url_for('info', request_id=request_id))
	return render_template('index.html')

@app.route('/info/<int:request_id>')
def info(request_id):
	pipe = cache.pipeline()
	pipe.get("test" + str(request_id) + "_url")
	pipe.get("test" + str(request_id) + "_load")
	pipe.get("test" + str(request_id) + "_time")
	answ = pipe.execute()
	url = str(answ[0].decode('utf-8'))
	load = int(answ[1].decode('utf-8'))
	max_time = int(answ[2].decode('utf-8'))
	if cache.get("test" + str(request_id) + "_OK") is None:
		x = threading.Thread(target=start_test, args=(url, load, request_id, max_time))
		x.start()
		return render_template('info.html', url=url, load=load,
		 time=max_time, ok=0, progress=cache.get("test" + str(request_id) + "_processing").decode('utf-8'), time_passed=0,
		 hit=0, miss=0, avg=0)
	hit = 0 if cache.get("test" + str(request_id) + "_Hit") is None else (int)(cache.get("test" + str(request_id) + "_Hit").decode('utf-8'))
	miss = 0 if cache.get("test" + str(request_id) + "_Miss") is None else (int)(cache.get("test" + str(request_id) + "_Miss").decode('utf-8'))
	avg = round((1000*(float)(cache.get("test" + str(request_id) + "_time_passed").decode('utf-8')))/(hit + miss),2)
	return render_template('info.html', url=url, load=load,
		 time=max_time, ok=cache.get("test" + str(request_id) + "_OK").decode('utf-8'),
		  progress=cache.get("test" + str(request_id) + "_processing").decode('utf-8'),
		  time_passed=cache.get("test" + str(request_id) + "_time_passed").decode('utf-8'),
		  hit = hit,
		  miss = miss,
		  avg = avg)


@app.route('/error/<id>')
def error(id):
	if int(id) == 1:
		error = "URL must be in such form: http://url.domain or http://url.domain:port_number"
		return render_template('error.html', error=error)
	if int(id) == 2:
		error = "Load must be an integer!"
		return render_template('error.html', error=error)
	if int(id) == 3:
		error = "Max time must be an integer!"
		return render_template('error.html', error=error)

if __name__ == "__main__":
	app.run(host="0.0.0.0")
