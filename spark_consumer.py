from pyspark.sql import SparkSession
from pyspark.sql.functions import col,from_json
from pyspark.sql.types import StructType ,StructField ,StringType ,IntegerType
spark = SparkSession.builder \
    .appName("KafkaSparkOrderWorkshop") \
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
target_df = json_df.withColumn("discounted_price", col("price") * 0.9)
query = target_df.writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", False) \
    .start()
query.awaitTermination()