package com.ning.demo.student;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** v3 接口回归测试：写请求同步携带幂等键。 */
@SpringBootTest
@AutoConfigureMockMvc
class StudentControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void shouldListPresetStudents() throws Exception {
        mockMvc.perform(get("/api/v1/students"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data", hasSize(3)));
    }

    @Test
    void shouldSearchByName() throws Exception {
        mockMvc.perform(get("/api/v1/students").param("name", "林"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].name").value("林晓雨"));
    }

    @Test
    void shouldCreateStudent() throws Exception {
        Map<String, String> body = Map.of(
                "studentNo", "20260004",
                "name", "陈晨",
                "gender", "FEMALE",
                "grade", "2026级",
                "phone", "13800000004",
                "email", "chenchen@example.test"
        );
        mockMvc.perform(post("/api/v1/students")
                        .header("X-Idempotency-Key", "create-student-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.id").isNumber())
                .andExpect(jsonPath("$.data.name").value("陈晨"));
    }

    @Test
    void shouldRejectInvalidStudent() throws Exception {
        mockMvc.perform(post("/api/v1/students")
                        .header("X-Idempotency-Key", "invalid-student-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"studentNo\":\"1\",\"name\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(10001));
    }
}

