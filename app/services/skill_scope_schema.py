JSON_RESUME_SCHEMA = {
	"source_file": "string",
	"basics": {
		"name": "string",
		"label": "string",
		"email": "string",
		"phone": "string",
		"url": "string",
		"summary": "string",
		"location": {
			"address": "string",
			"postalCode": "string",
			"city": "string",
			"countryCode": "string",
			"state": "string"
		},
		"profiles": [{
			"network": "string",
			"username": "string",
			"url": "string"
		}]
	},
	"work": [{
		"name": "string",
		"position": "string",
		"url": "string",
		"startDate": "YYYY-MM-DD",
		"endDate": "YYYY-MM-DD",
		"is_current": "boolean",
		"role_order": "integer",
		"summary": "string",
		"highlights": [
			"string"
		]
	}],
	"volunteer": [{
		"organization": "string",
		"position": "string",
		"url": "string",
		"startDate": "YYYY-MM-DD",
		"endDate": "YYYY-MM-DD",
		"summary": "string",
		"highlights": [
			"string"
		]
	}],
	"education": [{
		"institution": "string",
		"url": "string",
		"area": "string",
		"studyType": "string",
		"startDate": "YYYY-MM-DD",
		"endDate": "YYYY-MM-DD",
		"score": "string",
		"courses": [
			"string"
		]
	}],
	"awards": [{
		"title": "string",
		"date": "YYYY-MM-DD",
		"awarder": "string",
		"summary": "string"
	}],
	"certificates": [{
		"name": "string",
		"date": "YYYY-MM-DD",
		"issuer": "string",
		"url": "string"
	}],
	"publications": [{
		"name": "string",
		"publisher": "string",
		"releaseDate": "YYYY-MM-DD",
		"url": "string",
		"summary": "string"
	}],
	"skills": [{
		"name": "string",
		"level": "string",
		"keywords": [
			"string"
		]
	}],
	"languages": [{
		"language": "string",
		"fluency": "string"
	}],
	"interests": [{
		"name": "string",
		"keywords": [
			"string"
		]
	}],
	"references": [{
		"name": "string",
		"reference": "string"
	}],
	"projects": [{
		"name": "string",
		"startDate": "YYYY-MM-DD",
		"endDate": "YYYY-MM-DD",
		"description": "string",
		"highlights": [
			"string"
		],
		"url": "string"
	}]
}

