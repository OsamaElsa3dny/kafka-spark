from pyspark.sql import SparkSession
from pyspark.sql.functions import col,from_json
from pyspark.sql.types import StructType ,StructField ,StringType ,IntegerType
spark = SparkSession.builder \
    .appName("KafkaSparkOrdersTask2") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.1") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

schema = StructType([
    StructField("customer",StringType(),True),
    StructField("product",StringType(),True),
    StructField("price",IntegerType(),True)
])

raw_df = spark.readStream.format("kafka").option("kafka.bootstrap.servers", "localhost:9092").option("subscribe", "orders").option("startingOffsets", "latest").load()
json_df = raw_df.selectExpr("CAST(value AS STRING)").select(from_json(col("value"), schema).alias("data")).select("data.*")
products_df = json_df.select("product")

query = products_df.writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", False) \
    .start()
query.awaitTermination()
