#Script para mandar los hepmc de los runs a la carpeta correspondiente
#!/bin/bash

folder_destiny="/home/cristian/Desktop/HEP_Jones/paper_2208/scripts_2208/data/raw"

tipos="ZH WH TTH"

for tipo in ${tipos}
	do
	#declare -a arr
	folder_origin="/home/cristian/Programs/MG5_aMC_v2_9_2/HN_${tipo}/Events"
	cd ${folder_origin}
	runs=( $(ls -d */) )
	for run in "${runs[@]}"
		do
		#echo "${run}"
		cd "${run}"
		count="$(ls -1 *.hepmc 2>/dev/null | wc -l)"
		#echo "${count}"
		if [ $count == 0 ]
			then
			#echo "hola"
			file_gz=("$(ls -d *.hepmc.gz)")
			gzip -dk "${file_gz}"
		fi
		file_mc=("$(ls -d *.hepmc)")
		echo "${file_mc}"
		file_final="$(echo "${file_mc}" | sed 's/_pythia8_events//')"
		cp "${file_mc}" "${folder_destiny}/run_${file_final}"	
		cd ..
	done
done
