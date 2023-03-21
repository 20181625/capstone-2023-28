package com.capstone.traffic.ui.home.direction

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.widget.*
import androidx.lifecycle.ViewModelProvider
import com.capstone.traffic.R
import com.capstone.traffic.databinding.ActivityDirectionBinding
import com.capstone.traffic.global.BaseActivity
import com.capstone.traffic.global.appkey.APIKEY
import com.capstone.traffic.model.network.kakao.place.Client
import com.capstone.traffic.model.network.kakao.place.Place
import com.capstone.traffic.model.network.kakao.place.Response
import com.capstone.traffic.model.network.kakao.place.Service
import com.capstone.traffic.model.network.sk.direction.dataClass.objects
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody
import retrofit2.Call
import retrofit2.Callback

class DirectionActivity : BaseActivity<ActivityDirectionBinding>() {
    override var layoutResourceId: Int = R.layout.activity_direction
    private lateinit var directionViewModel: DirectionViewModel
    var listAdapter : ArrayAdapter<String>? = null
    var placeData : List<Place>? = null
    var nameData : List<String>? = null
    var startCoor : Pair<String, String> = Pair("","")
    var endCoor : Pair<String, String> = Pair("","")

    override fun initBinding() {
        directionViewModel = ViewModelProvider(this)[DirectionViewModel::class.java]
        binding.direction = directionViewModel


        var contentView: View = (getSystemService(Context.LAYOUT_INFLATER_SERVICE) as LayoutInflater).inflate(R.layout.dialog_slide_up, null)
        val slideupPopup = SlideUpDialog.Builder(this)
            .setContentView(contentView)
            .create()


        listAdapter = ArrayAdapter(
            this,
            android.R.layout.simple_list_item_1,
        )
        contentView.findViewById<ListView>(R.id.search_lv).adapter = listAdapter

        val searchView = contentView.findViewById<SearchView>(R.id.search_sv)
        searchView?.setOnQueryTextListener(object : SearchView.OnQueryTextListener {
            override fun onQueryTextSubmit(query: String?): Boolean {
                return false
            }

            override fun onQueryTextChange(newText: String?): Boolean {
                if(newText != null) getKakaoApi(newText)
                else{
                    listAdapter?.clear()
                }
                return false
            }
        })
        contentView.findViewById<ListView>(R.id.search_lv).onItemClickListener =
            AdapterView.OnItemClickListener { parent, view, position, id ->
                val txt = parent.getItemAtPosition(position).toString()
                if (contentView.findViewById<TextView>(R.id.name).text == "도착지 검색"){
                    endCoor = findXY(txt)
                    binding.endEt.text = txt
                }
                else{
                    startCoor = findXY(txt)
                    binding.startEt.text = txt
                }
                slideupPopup.dismissAnim()
                searchFillCheck()
            }
        binding.endEt.setOnClickListener{
            slideupPopup.show()
            contentView.findViewById<TextView>(R.id.name).text = "도착지 검색"
            contentView.findViewById<SearchView>(R.id.search_sv).setQuery("",false)
            listAdapter?.clear()
            listAdapter?.notifyDataSetChanged()
            contentView.findViewById<Button>(R.id.close).setOnClickListener {
                slideupPopup.dismissAnim()
            }
        }

        binding.startEt.setOnClickListener{
            slideupPopup.show()
            contentView.findViewById<TextView>(R.id.name).text = "출발지 검색"
            listAdapter?.clear()
            contentView.findViewById<SearchView>(R.id.search_sv).setQuery("",false)
            listAdapter?.notifyDataSetChanged()
            contentView.findViewById<Button>(R.id.close).setOnClickListener {
                slideupPopup.dismissAnim()
            }
        }
    }
    private fun findXY(name : String) : Pair<String, String>{
        placeData?.forEach {
            if(it.place_name == name) return Pair(it.x, it.y)
        }
        return Pair("","")
    }
    private fun searchFillCheck() : Boolean
    {
        if(binding.startEt.text == "" || binding.endEt.text == ""){
            return false
        }
        getSkApi()
        Toast.makeText(this,"${startCoor.first} ${startCoor.second}",Toast.LENGTH_LONG).show()
        return true
    }

    private fun getPlaceData(datas : List<Place>)
    {
        placeData = datas
        val tmp = mutableListOf<String>()
        listAdapter?.clear()
        datas.forEach {
            tmp.add(it.place_name)
            listAdapter?.add(it.place_name)
        }
        nameData = tmp
        listAdapter?.notifyDataSetChanged()
    }
    private fun getKakaoApi(place : String) {
        val retrofit = Client.getInstance()
        val service = retrofit.create(Service::class.java)
        val key = "KakaoAK ${APIKEY.KAKAO_APIKEY}"
        service.getResponse(key,"1","10","accuracy",place)
            .enqueue(object : Callback<Response> {
                override fun onResponse(call: Call<Response>, response: retrofit2.Response<Response>) {
                    if(response.isSuccessful){
                        if(response.body() != null ) getPlaceData(response.body()!!.documents)
                    }
                }
                override fun onFailure(call: Call<Response>, t: Throwable) {
                    print(1)
                }
            })
    }

    private fun getSkApi(){
        val retrofit = com.capstone.traffic.model.network.sk.direction.Client.getInstance()
        val service = retrofit.create(com.capstone.traffic.model.network.sk.direction.Service::class.java)
        val mediaType = "application/json".toMediaTypeOrNull()
        val param  = RequestBody.create(mediaType,"{\"startX\":\"${startCoor.first}\",\"startY\":\"${startCoor.second}\",\"endX\":\"${endCoor.first}\",\"endY\":\"${endCoor.second}\",\"lang\":0,\"format\":\"json\",\"count\":10}")
        service.getDirection(param = param)
            .enqueue(object : Callback<objects>{
                override fun onResponse(
                    call: Call<objects>,
                    response: retrofit2.Response<objects>
                ) {
                    if(response.isSuccessful){

                    }
                }

                override fun onFailure(call: Call<objects>, t: Throwable) {
                    print(1)
                }
            })

    }
}