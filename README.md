# Melawai-Test

Sitem pencarian dokumen dengan sistem chatbot menggunakan AI.

AI yang digunakan llama-3.3-70b-versatile

# Link Video Live Demo 

[Video Live Demo](https://drive.google.com/file/d/1Zw38Smt84flfTk7Pszgm8CRqoCQGeYx1/view)


# API
| EndPoint  | Description                                           | Method    |
| ---        | ---                                                  | ---       |
| /ingest   | Untuk mengupload document dan dirubah menjadi vektor  | Post      |
| /chat     | Untuk menanyakan menanyakan AI mengenai document      | Post      |
| /vec_data | Untuk melihat data di dalam database Vector           | Get       |
| /vec_data | Untuk delete data di dalam database Vector            | Delete    |

## Ingest

### Request

Body (multipart form):
    file - untuk upload file 

### Response 

Status Code:
    201 (created)

Response Body: 

```json
{
  "document_id": 0,
  "file_name": "string",
  "total_chunk": 0
}
```

## Chat

### Request 

Body (json) : 

  ```json
  {
  "msg": "string"
  }
  ```

### Response

Status Response:
    200

Response Body: 

```json 
{
"msg": "string"
} 
```

## Vec_data

### Get

#### Request 

No Request

#### Response 

status response: 
    200

Response Body:

```json
[
  {
    "id": "string",
    "Content": "string",
    "Metadata": {
      "headings": "string",
      "file_name": "string",
      "page_start": int,
      "page_end": int,
      "page_numbers": [],
      "chunk_index": int,
      "document_id": int
    }
  }
] 
```

### Delete

#### Request 

Body (json):

```json
{
  "ids": [
    "string"
  ],
  "metadata": {
    "additionalProp1": {}
  }
}
```

#### Response

status response: 
    204 (no content)


# Strategi Parsing dan Chunking

Untuk kasus parsing dokumen yang memiliki struktur, saya memilih library docling. Dikarenakan libary ini menyedikan pembacaan struktur dokument dan secara otomatis dapat membagi content dengan header.

Selain itu fitur chunking pada project ini saya menggunakan langchain text splitter. Untuk cara kerjanya adalah dengan membagi per heading (dimana sebelemunya docling sudah merubah menjadi markdown dan memiliki heading). Setelahnya di setiap heading akan dipotong berdasarkan tokenizer dengan size 300 dan tambahan overlap 40.

# System Prompt

AI menggunakan role sebagai asisten Q&A yang mana AI hanya boleh menjawab seputar dokumen yang di sediakan, jika tidak akan menjawab "Maaf, saya hanya bisa menjawab terkait kebijakan internal.". Selain itu AI juga harus memberikan bukti kepada user berupa page, title, dan section dari mana untuk mengurangi tingkat halusinasi.


# Future Scale Up to Azure/Fabric

Disini saya menggunakan database SQLLite yang mana digunakan untuk menyimpan document Id atau kebutuhan UI kedepannya. Jika user ingin menghapus dokumen, data vektor akan mudah terhapus. SQLLite dapat diubah menjadi Azure SQL Database

Selain itu untuk parser dapat dirubah menjadi azure document intelligence yang mana jauh lebih bagus dan akurat dibandingkan dengan docling.

Untuk Script python dapat dibungkus kedalam docker dengan menggunakan 2 tahap build. Build pertama untuk install depedency (biasanya digunakan pada saat update dependecy) dan build kedua dikenal sebagai runner untuk update code. Dengan cara ini code dapat dijalankan dengan lebih cepat, tanpa perlu menunggu update dependecy. Hosting server dapat di Virtual Machine Azure yang dijalankan menggunakan linux. 
