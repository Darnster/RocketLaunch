def lambda_handler(event, context):
	test = False
	if test:
		import main_test
		main_test.process()
	else:
		import main
		main.process()