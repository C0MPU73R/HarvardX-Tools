#!/nfs/projects/c/ci3_jwaldo/MONGO/bin/python
"""
This is generic CSV to JSON converter containing newline delimited formatting

Input is a comma delimited CSV file
Output is a newline delimited JSON formatted

Usage:
python convertCSVtoJSON [-options]

OPTIONS:
--input Name of input filename
--output Name of output filename
--gzip Gzip output json file
--schema Specify JSON Schema (Optional)
--schema-name Specify JSON Schema name within json file, if it exists

class functions:
def cleanJSONline(self, d, schema_dict): # Main Clean
def applySchemaFormat(self, value, specified_type):
def checkIllegalKeys(self, d, fixkeys=True):
def readSchema(self, schema_file=None, schema_name=None):
def writeJSONline(self, x, fileHandler, schema_dict):
def writeOutJSONfile(self, writeData, outputfilename, gzipOutput, schema_file=None, schema_name=None):
def printOtherStats(self):
def calculateOverallSummary(self):
def calculateSchemaStats(self):
def printSchemaStats(self):
def printSchemaStatsPerRow(self, row):

@author: G.Lopez
"""

import os
import sys
import csv
import json
import gzip
from collections import OrderedDict
from path import path
import argparse
import pandas as pd


# List of supported file types
ZIP_EXT = '.gz'
SUPPORTED_FILE_EXT = ['.csv', '.csv.gz']

# BigQuery to Python Type
BQ2PTYPE = {'RECORD': dict, 'INTEGER': int, 'STRING': unicode, 'FLOAT': float, 
            'BOOLEAN': int,
            'TIMESTAMP': unicode,
           }

# Define Schema Stats
SCHMA_SUMMARY_COLS = ['Correct', 'Incorrect', 'Fixed', 'Not Fixed', '% Incorrect', '% Corrected']

# Replace illegal characters in key field names
# These characters are not accepted as BigQuery table field names and need to be fixed
DASH = '-'
PERIOD = '.'
REPLACE = {DASH: '_',
           PERIOD: '__'
          }

class convertCSVtoJSON(object):

	def __init__(self):

		# Initialize options to None
		self.writeData = None
		self.outputfilename = None
		self.gzipOutput = None
		self.schema_file = None
		self.schema_name = None

		# Maintain Intermediate Stats / Counting
		self.LINE_CNT = 0
		self.LINE_CNT_1000 = 1000
		self.NONE_CNT_DICT = {}	 # Empty Fields Count
		self.VALUE_CNT_DICT = {}	 # Non-Empty Fields Count
		self.SCHMA_OK_CNT_DICT = {}   # Schema matches field format
		self.SCHMA_NOK_CNT_DICT = {}  # Schema doesn't match field format
		self.SCHMA_CVT_CNT_DICT = {}  # Non-matching field converted to Schema Format
		self.SCHMA_NCVT_CNT_DICT = {}  # Non-matching field could NOT be converted to Schema Format
		self.SCHMA_BAD_KEY = {}
		self.SCHMA_FIXED_KEYS = {}
		self.SCHMA_SUMMARY = pd.DataFrame( columns=SCHMA_SUMMARY_COLS  )

		# Maintain Overall stats	
		self.total_pop_fields = 0
		self.total_pop_fields_correct = 0
		self.total_pop_fields_incorrect = 0
		self.total_pop_fields_corrected = 0
		self.total_pop_fields_notcorrected = 0
		self.total_pop_fields_bad = 0
		self.pct_correct = 0
		self.pct_incorrect = 0
		self.pct_incorrect_fixed = 0
		self.pct_incorrect_notfixed = 0
		self.pct_bad_unknown = 0

	def cleanJSONline(self, d, schema_dict, applySchema=True):
		"""
		First, Delete keys with the value ``None`` in a dictionary, recursively.
		Second, Check Schema for keys that exist, if schema dictionary is specified
		"""

		# d.iteritems isn't used as you can't del or the iterator breaks.
		for key, value in d.items():

			if value is None:
				del d[key]

				# Record for stats
				if key not in self.NONE_CNT_DICT:
					self.NONE_CNT_DICT[key] = 1            
				else:
					self.NONE_CNT_DICT[key] += 1

			elif isinstance(value, dict):
				self.cleanJSONline(value, schema_dict)

			else:
		
				# Record stats for populated field
				if key not in self.VALUE_CNT_DICT:
					self.VALUE_CNT_DICT[key] = 1
				else:
					self.VALUE_CNT_DICT[key] += 1

				# If schema is specified, then attempt to convert incorrect fields into correct format
				if schema_dict is not None: 
					if key in schema_dict.keys():
	
						specified_type = BQ2PTYPE[schema_dict[key]]

						# Mismatch identified
						if type(value) in [float, int, unicode] and type(value) != specified_type:
				
							# Record stats for populated field with incorrect format
							if key not in self.SCHMA_NOK_CNT_DICT:
								self.SCHMA_NOK_CNT_DICT[key] = 1
							else:
								self.SCHMA_NOK_CNT_DICT[key] += 1
		      
							# Attempt to convert incorrect fields according to specified schema
							if applySchema:
								try:
									d[key] = self.applySchemaFormat(value, specified_type)
									# Record stats for populated field wit incorrect format and successfully converted field
									if key not in self.SCHMA_CVT_CNT_DICT:
										self.SCHMA_CVT_CNT_DICT[key] = 1
									else:
										self.SCHMA_CVT_CNT_DICT[key] += 1
								except:

									# Record stats for populated field wit incorrect format and unconverted field
									if key not in self.SCHMA_NCVT_CNT_DICT:
										self.SCHMA_NCVT_CNT_DICT[key] = 1
									else:
										self.SCHMA_NCVT_CNT_DICT[key] += 1

									continue

						# Schema and current field format matches
						else:

							if key not in self.SCHMA_OK_CNT_DICT:
								self.SCHMA_OK_CNT_DICT[key] = 1
							else:
								self.SCHMA_OK_CNT_DICT[key] += 1

					# Key does not exist in defined schema 
					else:

						if key not in self.SCHMA_BAD_KEY:
							self.SCHMA_BAD_KEY[key] = 1
						else:
							self.SCHMA_BAD_KEY[key] += 1

					continue
		return d


	def applySchemaFormat(self, value, specified_type):
		"""
		This function will compare the current key value field to the specified format schema for this field
		and then an attempt to convert will be performed. If successful, return value and assign it. Otherwise,
		raise an error
		"""
		if type(value) is float and specified_type is int:

			try:
				new_value = int(value) 
			except:
				raise

		elif type(value) is int and specified_type is float:

			try:
				new_value = float(value)
			except:
				raise

		elif type(value) is unicode and specified_type is int:
			try:
				new_value = int(float(value.encode("ascii")))
			except:
				pass
				try:
					new_value = int(value.encode("ascii"))
				except:
					raise

		elif type(value) is unicode and specified_type is float:
			try:
				new_value = float(value.encode("ascii"))
			except:
				raise

		elif type(value) is float and specified_type is unicode:
			try:
				new_value = str(value)
			
			except:
				raise
			
		else:
			print "[applySchemaFormat]: Format not handled: value %s, spec_type %s" % (type(value), specified_type)
			raise

		return new_value

	def checkIllegalKeys(self, d, fixkeys=True):
		"""
		This function will check for illegal keys according to the REPLACE dictionary.
		Optionally, fix the keys according to the dictionary to prevent illegal keys when importing into BigQuery
		"""
		illegal_keys_exist = False

		# Lastly, check for illegal characters in keys and replace
		for key, value in d.items():
			if DASH in key or PERIOD in key:
				illegal_keys_exist = True
				illegal_key = key
				new_key = key.replace(DASH, REPLACE[DASH]).replace(PERIOD, REPLACE[PERIOD])
				if illegal_key not in self.SCHMA_BAD_KEY:
					self.SCHMA_BAD_KEY[illegal_key] = new_key
				if new_key not in self.SCHMA_FIXED_KEYS:
					self.SCHMA_FIXED_KEYS[new_key] = 1
				else:
					self.SCHMA_FIXED_KEYS[new_key] += 1

		if illegal_keys_exist and fixkeys:
			# Need to rebuild ordered dict
			goodkeys = OrderedDict((self.SCHMA_BAD_KEY[k] if k in self.SCHMA_BAD_KEY else k, v) for k, v in d.iteritems())
			return goodkeys
		else:
			return d
			    
	def readSchema(self, schema_file=None, schema_name=None):
		'''
		Function will read the specified schema and will be used for comparing each json key/value pair
		'''
		if schema_name is None:
			schema = json.loads(open(schema_file).read())
		else:
			schema = json.loads(open(schema_file).read())[schema_name]

		schema_dict = OrderedDict()
		for keys in schema:
			schema_dict[keys.get('name', None)] = keys.get('type', None)

		print "--------------------------------"
		print "SCHEMA SPECIFIED"
		print "--------------------------------"
		print(json.dumps(schema_dict, indent=4))

		return schema_dict


	def writeJSONline(self, x, fileHandler, schema_dict):
		"""
		Write out single newline delimited JSON line output, while maintaining column ordering
		"""

		try:
			# Process rows and writ out
			rec = x.to_json(orient="index", force_ascii=True)
			rec_json = json.loads(rec, object_pairs_hook=OrderedDict)
			rec_json_cleaned = self.cleanJSONline(rec_json, schema_dict)
			rec_json_cleaned_verified_keys = self.checkIllegalKeys(rec_json_cleaned)
			fileHandler.write(json.dumps(rec_json_cleaned_verified_keys) + "\n")

			# Print procesing Counter
			self.LINE_CNT = self.LINE_CNT + 1
			if self.LINE_CNT % self.LINE_CNT_1000 == 0:
				sys.stdout.write("[main]: %dk Lines processed\r" % (self.LINE_CNT / self.LINE_CNT_1000 ) )
				sys.stdout.flush()
		except:
			print "[main]: Error writing json line %s\n" % rec
			pass 

	def writeOutJSONfile(self, writeData, outputfilename, gzipOutput, schema_file=None, schema_name=None):
		"""
		Create JSON file based on options for --output and --gzip
		""" 
		if gzipOutput:
			ofp = gzip.GzipFile(outputfilename, 'w')
		else:
			ofp = open(outputfilename, 'w')

		schema_dict = None
		if schema_file is not None:
			schema_dict = self.readSchema(path(schema_file), schema_name)

		writeData.apply(self.writeJSONline, args=[ofp, schema_dict], axis=1)
	    
		(self.rows, self.cols) = writeData.shape
		self.outputfilename = outputfilename

	def printOtherStats(self):
		"""
		Print missing field and value statistics
		"""
		print "--------------------------------"
		print "MISSING FIELDS SUMMARY"
		print "--------------------------------"
		if self.NONE_CNT_DICT:
			for field in sorted(self.NONE_CNT_DICT, key=self.NONE_CNT_DICT.get, reverse=True):
				print "[main]: Field name: %s, None/Null count: %s" % (field, self.NONE_CNT_DICT[field])
		
		print "--------------------------------"
		print "VALUE FIELDS SUMMARY"
		print "--------------------------------"
		if self.VALUE_CNT_DICT:
			for field in sorted(self.VALUE_CNT_DICT, key=self.VALUE_CNT_DICT.get, reverse=True):
				print "[main]: Field name: %s, Value count: %s" % (field, self.VALUE_CNT_DICT[field])

	def printOverallSummary(self):
		"""
		Print Overall Summary including % correct vs. incorrect. Of those incorrect, what % was fixed and not fixed
		"""

		print "--------------------------------"
		print "SUMMARY"
		print "--------------------------------"
		if self.outputfilename is not None and self.rows is not None and self.cols is not None:
			print "[main]: Finished writing JSON file %s with %s rows and %s fields max" % (self.outputfilename, self.rows, self.cols)

		print "[main]: Total Populated Fields = %s" % self.total_pop_fields
		print "[main]: Total Populated Fields Correct = %s" % self.total_pop_fields_correct
		print "[main]: Total Populated Fields Incorrect = %s" % self.total_pop_fields_incorrect
		print "[main]: Total Populated Fields Corrected = %s" % self.total_pop_fields_corrected
		print "[main]: Total Populated Fields Not Corrected = %s" % self.total_pop_fields_notcorrected
		print "[main]: Total Populated Bad/Unknown Fields = %s" % self.total_pop_fields_bad

		print "[main]: Pct Correct = %0.2f%%" % self.pct_correct
		print "[main]: Pct InCorrect = %0.2f%%" % self.pct_incorrect
		print "[main]: Pct InCorrect Fixed = %0.2f%%" % self.pct_incorrect_fixed
		print "[main]: Pct InCorrect Not Fixed= %0.2f%%" % self.pct_incorrect_notfixed
		print "[main]: Pct Bad/Unknown Fields Not Fixed = %0.2f%%" % self.pct_bad_unknown

	def calculateOverallSummary(self):
		"""
		Function to calculate Overall Stats
		"""

		self.pct_correct = float(float(self.total_pop_fields_correct) / float(self.total_pop_fields)) * 100.00 if self.total_pop_fields != 0 else 0.0
		self.pct_incorrect = float(float( self.total_pop_fields_incorrect) / float(self.total_pop_fields)) * 100.00 if self.total_pop_fields != 0 else 0.0
		self.pct_incorrect_fixed = float( float(self.total_pop_fields_corrected) / float(self.total_pop_fields_incorrect) ) * 100.00 if self.total_pop_fields_incorrect != 0 else 0.0
		self.pct_incorrect_notfixed = float( float(self.total_pop_fields_notcorrected) / float(self.total_pop_fields_incorrect) ) * 100.00 if self.total_pop_fields_incorrect != 0 else 0.0
		self.pct_bad_unknown = float( float(self.total_pop_fields_bad) / float(self.total_pop_fields) ) * 100.00 if self.total_pop_fields != 0 else 0.0

	def calculateSchemaStats(self):
		"""
		Function to calculate Schema Stats
		"""

		if self.VALUE_CNT_DICT:
			for field in sorted(self.VALUE_CNT_DICT, key=self.VALUE_CNT_DICT.get, reverse=True):
				total_pop_fields = self.VALUE_CNT_DICT.get(field, 0) 	           # VALUE_CNT_DICT[field]
				total_pop_fields_correct = self.SCHMA_OK_CNT_DICT.get(field, 0)         # SCHMA_OK_CNT_DICT[field]
				total_pop_fields_incorrect = self.SCHMA_NOK_CNT_DICT.get(field, 0)      # SCHMA_NOK_CNT_DICT[field]
				total_pop_fields_corrected = self.SCHMA_CVT_CNT_DICT.get(field, 0)      # SCHMA_CVT_CNT_DICT[field]
				total_pop_fields_notcorrected = self.SCHMA_NCVT_CNT_DICT.get(field, 0)  # SCHMA_NCVT_CNT_DICT[field]
				pct_correct = float(float(total_pop_fields_correct) / float(total_pop_fields)) * 100.00 if total_pop_fields != 0 else 0.0
				pct_incorrect = float(float( total_pop_fields_incorrect) / float(total_pop_fields)) * 100.00 if total_pop_fields != 0 else 0.0
				pct_incorrect_fixed = float( float(total_pop_fields_corrected) / float(total_pop_fields_incorrect) ) * 100.00 if total_pop_fields_incorrect != 0 else 0.0
				pct_incorrect_notfixed = float( float(total_pop_fields_notcorrected) / float(total_pop_fields_incorrect) ) * 100.00 if total_pop_fields_incorrect != 0 else 0.0
				self.SCHMA_SUMMARY.ix[field, 'Field'] = field
				self.SCHMA_SUMMARY.ix[field, 'Correct'] = total_pop_fields_correct
				self.SCHMA_SUMMARY.ix[field, 'Incorrect'] = total_pop_fields_incorrect
				self.SCHMA_SUMMARY.ix[field, 'Fixed'] = total_pop_fields_corrected
				self.SCHMA_SUMMARY.ix[field, 'Not Fixed'] = total_pop_fields_notcorrected
				self.SCHMA_SUMMARY.ix[field, '% Incorrect'] = pct_incorrect
				self.SCHMA_SUMMARY.ix[field, '% Corrected'] = pct_incorrect_fixed

				# Maintain overall count
				self.total_pop_fields = self.total_pop_fields + total_pop_fields
				self.total_pop_fields_correct = self.total_pop_fields_correct + total_pop_fields_correct
				self.total_pop_fields_incorrect = self.total_pop_fields_incorrect + total_pop_fields_incorrect
				self.total_pop_fields_corrected = self.total_pop_fields_corrected + total_pop_fields_corrected
				self.total_pop_fields_notcorrected = self.total_pop_fields_notcorrected + total_pop_fields_notcorrected

	def printSchemaStats(self):
		"""
		Function to print Schema Stats
		"""

		# Print stats for schema verification
		print "--------------------------------"
		print "SCHEMA CHECK SUMMARY"
		print "--------------------------------"

		# Sort by % not fixed to identify problem areas
		self.SCHMA_SUMMARY.sort(['% Incorrect'], inplace=True, ascending=False)
		self.SCHMA_SUMMARY.apply(self.printSchemaStatsPerRow, axis=1)

		# Print Bad Keys, if they exist
		if self.SCHMA_BAD_KEY:
			for field in self.SCHMA_BAD_KEY:
				if type(self.SCHMA_BAD_KEY[field]) is int:
					print "[main]: Bad Field name: %s, %s values ignored since does not exist in schema" % (field, self.SCHMA_BAD_KEY[field])
					self.total_pop_fields_bad = self.total_pop_fields_bad + self.SCHMA_BAD_KEY[field]
				if type(self.SCHMA_BAD_KEY[field]) is unicode:
					print "[main]: Bad Field name: %s replaced with %s (Fixed %s occurrences)" % (field, self.SCHMA_BAD_KEY[field], self.SCHMA_FIXED_KEYS[self.SCHMA_BAD_KEY[field]])
					self.total_pop_fields_bad = self.total_pop_fields_bad + self.SCHMA_BAD_KEY[field]

	def printSchemaStatsPerRow(self, row):
		"""
		Help function to print stats for each field
		"""
	    
		print "[main]: Field name: %s, Correct: %s, Incorrect: %s, Fixed: %s, Not Fixed: %s (%0.2f%% incorrect, %0.2f%% corrected)" % ( row['Field'], row['Correct'], row['Incorrect'], row['Fixed'], row['Not Fixed'], row['% Incorrect'], row['% Corrected'] )


def main():
	"""
	Main Convert CSV to JSON program 
	""" 
	global NONE_CNT_DICT, VALUE_CNT_DICT

	# Setup Command Line Options
	text_help = '''usage: %prog [-options] '''
	text_description = ''' Convert CSV to JSON script '''
	parser = argparse.ArgumentParser( prog='PROG',
				  description=text_description)
	parser.add_argument("--input", type=str, help="Name of input file", required=True)
	parser.add_argument("--output", type=str, help="Name of output file", required=True)
	parser.add_argument("--gzip", help="Gzip output file", action="store_true")
	parser.add_argument("--schema", type=str, help="Specify JSON Schema")
	parser.add_argument("--schema-name", type=str, help="Specify JSON Schema Name")
	args = vars(parser.parse_args())
	print "[main]: arguments passed => %s" % args

	# Read Input File
	print "[main]: Reading CSV input file %s " % args['input']
	try:
		if os.path.exists(args['input']):
			for ext in SUPPORTED_FILE_EXT:
				if ext in args['input'] and args['input'].endswith(ZIP_EXT):
					inputData = pd.read_csv(gzip.GzipFile(args['input']), sep=",")
					break
				elif ext in args['input']:
					inputData = pd.read_csv(args['input'], sep=",")
					break
				else:
					print "[main]: File type not supported"
					exit()
		else:
			print "[main]: File does not exist"
			exit()
	except:
		print "[main]: Error reading file"
		raise

	# Convert to JSON
	try:
		# Process Input
		converter = convertCSVtoJSON()
		converter.writeOutJSONfile(inputData, args['output'], args['gzip'], args['schema'], args['schema_name'] )

		# Print stats for missing/null data, Print stats for populated data
		converter.printOtherStats()
		converter.calculateSchemaStats()
		converter.printSchemaStats()

		# Print Final Summary
		converter.calculateOverallSummary()
		converter.printOverallSummary()
	except:
		print "[main]: ERROR => Failed to write JSON output"
		raise

if __name__ == '__main__':
	main()
