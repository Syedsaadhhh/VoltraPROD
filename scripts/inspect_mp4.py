import struct
from pathlib import Path

def parse_mp4(filepath: Path):
    with open(filepath, "rb") as f:
        data = f.read()

    print(f"Total file size: {len(data)} bytes")
    
    pos = 0
    boxes = []
    while pos < len(data) - 8:
        size, b_type = struct.unpack(">I4s", data[pos:pos+8])
        b_type_str = b_type.decode("ascii", errors="ignore")
        if size == 1: # 64-bit size
            size = struct.unpack(">Q", data[pos+8:pos+16])[0]
        elif size == 0:
            size = len(data) - pos
        boxes.append((b_type_str, pos, size))
        if size < 8:
            break
        pos += size

    print("Top-level boxes:", [b[0] for b in boxes])
    
    # Locate moov box
    moov_pos = None
    moov_size = None
    for b, p, s in boxes:
        if b == "moov":
            moov_pos = p
            moov_size = s
            break
            
    if not moov_pos:
        print("No moov box found at top level.")
        return

    # Scan inside moov
    moov_data = data[moov_pos+8:moov_pos+moov_size]
    sub_pos = 0
    tracks = []
    timescale = 1000
    duration = 0
    while sub_pos < len(moov_data) - 8:
        s_size, s_type = struct.unpack(">I4s", moov_data[sub_pos:sub_pos+8])
        s_type_str = s_type.decode("ascii", errors="ignore")
        if s_size < 8:
            break
        sub_box_data = moov_data[sub_pos+8:sub_pos+s_size]
        
        if s_type_str == "mvhd":
            version = sub_box_data[0]
            if version == 0:
                mvhd_timescale, mvhd_dur = struct.unpack(">II", sub_box_data[12:20])
            else:
                mvhd_timescale = struct.unpack(">I", sub_box_data[20:24])[0]
                mvhd_dur = struct.unpack(">Q", sub_box_data[24:32])[0]
            timescale = mvhd_timescale
            duration = mvhd_dur
            print(f"Header: timescale={timescale}, duration={duration} ({duration/timescale:.3f}s)")
            
        elif s_type_str == "trak":
            # Search inside trak for tkhd, mdia -> mdhd, minf -> stbl
            trak_data = sub_box_data
            t_pos = 0
            width, height = 0, 0
            t_dur = 0
            stts_entries = []
            stss_entries = []
            handler_type = ""
            
            while t_pos < len(trak_data) - 8:
                t_size, t_type = struct.unpack(">I4s", trak_data[t_pos:t_pos+8])
                t_type_str = t_type.decode("ascii", errors="ignore")
                if t_size < 8:
                    break
                t_box_data = trak_data[t_pos+8:t_pos+t_size]
                
                if t_type_str == "tkhd":
                    version = t_box_data[0]
                    if version == 0:
                        w_fixed, h_fixed = struct.unpack(">II", t_box_data[76:84])
                    else:
                        w_fixed, h_fixed = struct.unpack(">II", t_box_data[88:96])
                    width = w_fixed >> 16
                    height = h_fixed >> 16
                    
                elif t_type_str == "mdia":
                    # Parse mdia
                    m_pos = 0
                    while m_pos < len(t_box_data) - 8:
                        m_size, m_type = struct.unpack(">I4s", t_box_data[m_pos:m_pos+8])
                        m_type_str = m_type.decode("ascii", errors="ignore")
                        if m_size < 8:
                            break
                        m_box_data = t_box_data[m_pos+8:m_pos+m_size]
                        if m_type_str == "hdlr":
                            handler_type = m_box_data[8:12].decode("ascii", errors="ignore")
                        elif m_type_str == "mdhd":
                            m_ver = m_box_data[0]
                            if m_ver == 0:
                                m_ts, m_d = struct.unpack(">II", m_box_data[12:20])
                            else:
                                m_ts = struct.unpack(">I", m_box_data[20:24])[0]
                                m_d = struct.unpack(">Q", m_box_data[24:32])[0]
                            t_dur = m_d / m_ts if m_ts else 0
                        elif m_type_str == "minf":
                            # find stbl
                            minf_pos = 0
                            while minf_pos < len(m_box_data) - 8:
                                mi_size, mi_type = struct.unpack(">I4s", m_box_data[minf_pos:minf_pos+8])
                                mi_type_str = mi_type.decode("ascii", errors="ignore")
                                if mi_size < 8:
                                    break
                                mi_data = m_box_data[minf_pos+8:minf_pos+mi_size]
                                if mi_type_str == "stbl":
                                    stbl_pos = 0
                                    while stbl_pos < len(mi_data) - 8:
                                        s_s, s_t = struct.unpack(">I4s", mi_data[stbl_pos:stbl_pos+8])
                                        s_t_str = s_t.decode("ascii", errors="ignore")
                                        if s_s < 8:
                                            break
                                        s_d = mi_data[stbl_pos+8:stbl_pos+s_s]
                                        if s_t_str == "stts":
                                            entry_count = struct.unpack(">I", s_d[4:8])[0]
                                            for idx in range(entry_count):
                                                cnt, delta = struct.unpack(">II", s_d[8+idx*8:16+idx*8])
                                                stts_entries.append((cnt, delta))
                                        elif s_t_str == "stss":
                                            entry_count = struct.unpack(">I", s_d[4:8])[0]
                                            for idx in range(entry_count):
                                                kf = struct.unpack(">I", s_d[8+idx*4:12+idx*4])[0]
                                                stss_entries.append(kf)
                                        stbl_pos += s_s
                                minf_pos += mi_size
                        m_pos += m_size
                t_pos += t_size
                
            total_samples = sum(cnt for cnt, _ in stts_entries)
            print(f"Track: type={handler_type}, dimensions={width}x{height}, duration={t_dur:.3f}s, total_frames={total_samples}")
            if stts_entries:
                fps = total_samples / t_dur if t_dur > 0 else 0
                print(f"  Frame rate: ~{fps:.2f} fps")
            if stss_entries:
                print(f"  Keyframe indices ({len(stss_entries)} keyframes): {stss_entries[:15]}")
                
        sub_pos += s_size

parse_mp4(Path("assets/raw/scene.mp4"))
