def do_task(request):
    data = 'Fail'
    if request.is_ajax():
        job = tasks.create_models.delay()
        request.session['task_id'] = job.id
        data = job.id
    else:
        data = 'This is not an ajax request!'
    
    json_data = json.dumps(data)
    return HttpResponse(json_data, mimetype='application/json')